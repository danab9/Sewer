import pysam
from collections import Counter
import pandas as pd
import numpy as np
from sys import argv
import glob
import os
import errno
"""
for sewer samples.
iterate over mapped and sorted bam files,
calculate mutations frequencies by pileup files.
"""


def frequency(mut_val, pos, pileup_df, depth_threshold):
    """
    return frequency of mut_val base in specified position.
    :type pos: object
    :param mut_val: mutation nucleotide (A,C,T,G,-)
    :param pos: position
    :param pileup_df: the pileup dataframe
    :param depth_threshold: minimum depth threshold. below that, frequency is 0.
    :return: frequency of mutation nucleotide in position (mut_depth/sum*100)
    """
    mut_val = 'del' if mut_val == '-' else mut_val
    total = pileup_df.loc[pos]['sum']
    if total:
        count = pileup_df.loc[pos][mut_val]
        if count > depth_threshold:
            freq = (count / total) * 100
        else:
            freq = 0.0
    else:
        freq = None
    return freq


if __name__ == '__main__':
    # user input
    bam_dir = argv[1]
    out_file = argv[2]
    min_depth = int(argv[3])
    refseq_path = argv[4]
    # preparations
    refseq_name = os.path.basename(refseq_path).strip('.fasta')
    # index refseq
    pysam.faidx(refseq_path)
    refseq_series = pd.Series([x for x in pysam.Fastafile(refseq_path).fetch(reference=refseq_name)])
    muttable = pd.read_csv("/data/projects/Dana/scripts/covid19/novelMutTable.csv")  # TODO: get from other location!

    uniq_lineages = set()
    for lin in muttable.lineage:
        for x in lin.split(','):
            uniq_lineages.add(x.strip())
    muttable_by_lineage = {x: muttable[muttable.lineage.str.contains(x)] for x in uniq_lineages}
    for lin, table in muttable_by_lineage.items():
        table.lineage = lin

    final_df = pd.concat([frame for frame in muttable_by_lineage.values()])

    all_tables = {}

    files_list = glob.glob(bam_dir + '/*.mapped.sorted.bam')

    # iterate all bam files:
    for file in files_list:
        pileup_table = pd.DataFrame(np.empty(shape=(29903, 6))*np.nan, columns=['C', 'A', 'G', 'T',  'N', 'del'],
                                    index=list(range(29903)))
        bam = pysam.AlignmentFile(file, 'rb')
        pileup_iter = bam.pileup(stepper='nofilter')
        # iterate over reads in each position and count nucleotides, Ns and deletions.
        for position in pileup_iter:
            c = Counter({'C': 0, 'A': 0, 'G': 0, 'T': 0, 'N': 0, 'del': 0})
            for pileupread in position.pileups:
                if not pileupread.is_del and not pileupread.is_refskip:
                    c[pileupread.alignment.query_sequence[pileupread.query_position].upper()] += 1
                elif pileupread.is_del:
                    c['del'] += 1
                elif pileupread.is_refskip:  # N?
                    c['N'] += 1
            pileup_table.loc[position.reference_pos] = pd.Series(c)
        # produce pileup table(for each bam): pos,A,C,T,G,N,del,totaldepth,
        pileup_table.index.name = 'pos'
        pileup_table['sum'] = pileup_table['A'] + pileup_table['C'] + pileup_table['T'] + pileup_table['G'] + \
                              pileup_table['del'] + pileup_table['N']

        pileup_table['ref'] = refseq_series
        pileup_table.to_csv('temp_pileuptable.csv')  # to remove after debug
        pileup_table['ref_freq'] = pileup_table.apply(lambda row: (row[row['ref']] / row['sum'])*100 if row['sum'] else 0.0, axis=1)
        # add sample to table
        file_name = file.strip('BAM/').strip('.mapped.sorted.bam')
        all_tables[file_name] = pileup_table
        final_df[file_name] = final_df.apply(lambda row: frequency(row['mut'], row['pos']-1, pileup_table, min_depth), axis=1)

    final_df = final_df.sort_values(["lineage", "gene"], ascending=(True, False))  # sort by:(1)lineage (2)gene(S first)
    final_df.to_csv(out_file)

    try:
        os.makedirs('results/mutationsPileups')
    except OSError as e:
        if e.errno == errno.EEXIST:
            print("directory results/mutationsPileups already exists, continuing.")
        else:
            raise
    # write pileup files that contain only positions mutations
    for name, table in all_tables.items():
        # keep only lines that: >1% frequency of non refseq mutation AND >=10 depth (line.sum)
        table['N_freq'] = table.apply(lambda row: (row['N']/row['sum'])*100 if row['sum'] else 0.0, axis=1)
        indexNames = table[(table['sum'] < 10) | (table['ref_freq'] > 99) | (table['N_freq'] > 99)].index
        table = table.drop(index=indexNames, columns=['N_freq'])
        table.reset_index(level=0, inplace=True)
        table.to_csv('results/mutationsPileups/'+name+'.csv', index=False)

    # create another surveillance table
    lineage_avg = final_df.drop('pos', axis=1).groupby('lineage').mean().transpose()
    # calculate frequency
    lineage_num_muts = final_df.groupby('lineage')['lineage'].count().to_frame().rename(columns={'lineage': 'total'})
    lineage_non_zero_count = final_df.drop(columns=['nucleotide','AA','gene','type','pos','REF','mut']).groupby('lineage').agg(lambda x: x.ne(0).sum())
    lineage_freq = lineage_num_muts.join(lineage_non_zero_count)


    for name in all_tables.keys():
        lineage_freq[name] /= lineage_freq['total'] * 100

    lineage_freq = lineage_freq.drop(columns='total').transpose()
    surv_table = lineage_freq.add_suffix(' freq').join(lineage_avg.add_suffix(' avg'))
    surv_table.to_csv('results/surveillance_table.csv')





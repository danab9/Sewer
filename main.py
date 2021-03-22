import pysam
from collections import Counter
import pandas as pd
import numpy as np

# file = pysam.AlignmentFile('s6519_Ashdod_Jan1.mapped.sorted.bam', "rb")
# file = pysam.AlignmentFile('s7510_S483_L002_001.mapped.sorted.bam', 'rb')
# df_pysam = pd.DataFrame(np.zeros(shape=(29903, 5)), columns=['C', 'A', 'G', 'T', 'del'], index=list(range(29903)))
muttable = pd.read_csv("novelMutTable.csv")
#
# pileup_iter = file.pileup(stepper='nofilter')
# for position in pileup_iter:
#     c = Counter({'C': 0, 'A': 0, 'G': 0, 'T': 0, 'del': 0})
#     for pileupread in position.pileups:
#         if not pileupread.is_del and not pileupread.is_refskip:
#             c[pileupread.alignment.query_sequence[pileupread.query_position].upper()] += 1
#         if pileupread.is_del:
#             c['del'] += 1
#     df_pysam.loc[position.reference_pos+1] = pd.Series(c)
#
# df_pysam.index.name = 'pos'
# df_pysam['sum'] = df_pysam['A'] + df_pysam['C'] + df_pysam['T'] + df_pysam['G'] + df_pysam['del']
# df_pysam.to_csv("pileup.csv")  # temporary file
# pysam code above works fine (:

df_pysam = pd.read_csv('pileup.csv')
# create lineages list
uniq_lineages = set()
for lin in muttable.lineage:
    for x in lin.split(','):
        uniq_lineages.add(x.strip())

# create dictionary: {lineage: muttable} (mutations table df for each lineage)
muttable_by_lineage = {x: muttable[muttable.lineage.str.contains(x)] for x in uniq_lineages}


def frequency(mut_val, pos, pileup_df):
    mut_val = 'del' if mut_val=='-' else mut_val
    if pileup_df.loc[pos-1]['sum']:
        val = pileup_df.loc[pos-1][mut_val] / pileup_df.loc[pos-1]['sum']
    else:
        val = 0.0
    return val*100


final_df = pd.concat([frame for frame in muttable_by_lineage.values()])
final_df['sample'] = final_df.apply(lambda row: frequency(row['mut'], row['pos'], df_pysam), axis=1)



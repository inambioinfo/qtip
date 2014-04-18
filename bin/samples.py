"""
samples.py

Some things that are easy to get from aligners:
1. Score of best alignment (AS:i) for an unpaired read or end
2. Score of second-best alignment (XS:i) for an unpaired read or end
3. Mapping quality (MAPQ) assigned by aligner
4. Implied fragment length for paired-end alignment (TLEN)

Some things that we can get from Bowtie 2 but are harder or impossible
to get from other aligners:
1. Score of second-best concordant alignment for a paired-end read
2. Maximum and minimum possible scores for alignments, for rescaling

This spurs us to the following decisions about our output format:
1. Alignment scores will be unscaled.  Maximum and minimum values will
   be NA by default, but non-NA when available.  Note that maximum and
   minimum are particularly valuable when putting scores on a common
   scale across various read lengths.
2. Second-best concordant alignment score will be NA by default,
   non-NA when available.  This is unfortunate since some models might
   depend on that value and will therefore have to include a special
   case for when it's not available.

Here's the output format.  It's CSV with numeric, integer and logical
data types.  It can be read in using read.csv in R.

For unpaired examples:
1. Score of best alignment (AS:i)
2. Score of second-best alignment (XS:i)
3. Minimum possible "valid" score (or NA if not available)
4. Maximum possible "valid" score (or NA if not available)
5. Length of read
6. Mapping quality (MAPQ)
7. Correct? (only non-NA if data is either training data or simulated
   input data)

For concordantly-aligned paired-end examples:
1. Mate 1: Score of best alignment (AS:i)
2. Mate 1: Score of second-best alignment (XS:i)
3. Mate 1: Minimum possible "valid" score (or NA if not available)
4. Mate 1: Maximum possible "valid" score (or NA if not available)
5. Mate 1: Length of read
6. Mate 1: Mapping quality (MAPQ)
7. Mate 2: Score of best alignment (AS:i)
8. Mate 2: Score of second-best alignment (XS:i)
9. Mate 2: Minimum possible "valid" score (or NA if not available)
10. Mate 2: Maximum possible "valid" score (or NA if not available)
11. Mate 2: Length of read
12. Mate 2: Mapping quality (MAPQ)
13. Score of best concordant paired-end alignment
14. Score of second-best concordant paired-end alignment
15. Fragment length
16. Mate 1: Correct? (only non-NA if data is either training data or
    simulated input data)
"""

import os
import csv
from read import Alignment
from itertools import izip

try:
    import numpypy as np
except ImportError:
    pass
import numpy as np


class UnpairedTuple(object):
    """ Unpaired training/test tuple.  I'm, perhaps unwisely, overloading it
        so it can also represent a bad-end alignment.  I.e. there's an
        optional "other end length" field that is 0 for unpaired alignments
        and >0 for bad-end alignments. """

    def __init__(self, rdname, rdlen, minv, maxv, bestsc, best2sc, mapq, ordlen=0):
        assert minv is None or minv <= bestsc <= maxv
        self.rdname = rdname            # read name
        self.rdlen = rdlen              # read len
        self.ordlen = ordlen            # read len of opposite end
        self.minv = minv                # min valid score
        self.maxv = maxv                # max valid score
        self.bestsc = bestsc            # best
        self.best2sc = best2sc          # 2nd-best score
        self.mapq = mapq                # original mapq

    def __iter__(self):
        return iter([self.rdname, self.bestsc, self.best2sc, self.minv, self.maxv, self.rdlen, self.mapq, self.ordlen])
    
    @classmethod
    def from_alignment(cls, al, ordlen=0):
        """ Create unpaired training/test tuple from Alignment object """
        secbest = al.secondBestScore
        if hasattr(al, 'thirdBestScore'):
            secbest = max(secbest, al.thirdBestScore)
        min_valid, max_valid = None, None
        if hasattr(al, 'minValid'):
            assert hasattr(al, 'maxValid')
            min_valid, max_valid = al.minValid, al.maxValid
        return cls(al.name, len(al), min_valid, max_valid, al.bestScore, secbest, al.mapq, ordlen)
    
    @classmethod
    def to_data_frame(cls, ptups, cor=None):
        """ Convert the paired-end tuples to a pandas DataFrame """
        from pandas import DataFrame
        names, rdlen, best1, best2, minv, maxv, mapq, ordlen = [], [], [], [], [], [], [], []
        for ptup in ptups:
            names.append(ptup.rdname)
            best1.append(ptup.bestsc)
            best2.append(ptup.best2sc)
            minv.append(ptup.minv)
            maxv.append(ptup.maxv)
            rdlen.append(ptup.rdlen)
            mapq.append(ptup.mapq)
            ordlen.append(ptup.ordlen)
        df = DataFrame.from_items([('name', names)
                                   ('best1', best1),
                                   ('best2', best2),
                                   ('minv', minv),
                                   ('maxv', maxv),
                                   ('rdlen', rdlen),
                                   ('mapq', mapq),
                                   ('ordlen', ordlen)])
        if cor is not None:
            df['correct'] = np.where(cor, 1, 0)
        return df


class PairedTuple(object):
    """ Concordant paired-end training/test tuple.  One per mate alignment. """
    def __init__(self, rdname1, rdlen1, minv1, maxv1,
                 bestsc1, best2sc1, mapq1,
                 rdname2, rdlen2, minv2, maxv2,
                 bestsc2, best2sc2, mapq2,
                 bestconcsc, best2concsc, fraglen):
        assert minv1 is None or minv1 <= bestsc1 <= maxv1
        assert minv2 is None or minv2 <= bestsc2 <= maxv2
        self.rdname1 = rdname1          # read name #1
        self.rdname2 = rdname2          # read name #2
        self.rdlen1 = rdlen1            # read len #1
        self.rdlen2 = rdlen2            # read len #2
        self.minv1 = minv1              # min valid score #1
        self.minv2 = minv2              # min valid score #2
        self.maxv1 = maxv1              # max valid score #1
        self.maxv2 = maxv2              # max valid score #2
        self.bestsc1 = bestsc1          # best #1
        self.bestsc2 = bestsc2          # best #2
        self.best2sc1 = best2sc1        # 2nd-best score #1
        self.best2sc2 = best2sc2        # 2nd-best score #2
        self.mapq1 = mapq1              # original mapq #1
        self.mapq2 = mapq2              # original mapq #2
        self.bestconcsc = bestconcsc    # best concordant
        self.best2concsc = best2concsc  # 2nd-best concordant
        self.fraglen = fraglen          # fragment length

    def __iter__(self):
        return iter([self.rdname1, self.bestsc1, self.best2sc1, self.minv1, self.maxv1, self.rdlen1, self.mapq1,
                     self.rdname2, self.bestsc2, self.best2sc2, self.minv2, self.maxv2, self.rdlen2, self.mapq2,
                     self.bestconcsc, self.best2concsc, self.fraglen])
    
    @classmethod
    def from_alignments(cls, al1, al2):
        """ Create unpaired training/test tuple from pair of Alignments """
        secbest1, secbest2 = al1.secondBestScore, al2.secondBestScore
        if hasattr(al1, 'thirdBestScore'):
            assert hasattr(al2, 'thirdBestScore')
            secbest1 = max(secbest1, al1.thirdBestScore)
            secbest2 = max(secbest2, al2.thirdBestScore)
        min_valid1, min_valid2 = None, None
        max_valid1, max_valid2 = None, None
        if hasattr(al1, 'minValid'):
            min_valid1, min_valid2 = al1.minValid, al2.minValid
            max_valid1, max_valid2 = al1.maxValid, al2.maxValid
        best_concordant_score, second_best_concordant_score = None, None
        if hasattr(al1, 'bestConcordantScore'):
            assert hasattr(al2, 'bestConcordantScore')
            assert hasattr(al1, 'secondBestConcordantScore')
            assert hasattr(al2, 'secondBestConcordantScore')
            assert al1.bestConcordantScore == al2.bestConcordantScore
            assert al1.secondBestConcordantScore == al2.secondBestConcordantScore
            best_concordant_score, second_best_concordant_score = \
                al1.bestConcordantScore, al1.secondBestConcordantScore
        return cls(al1.name, len(al1), min_valid1, max_valid1, al1.bestScore,
                   secbest1, al1.mapq,
                   al2.name, len(al2), min_valid2, max_valid2, al2.bestScore,
                   secbest2, al2.mapq,
                   best_concordant_score, second_best_concordant_score,
                   Alignment.fragment_length(al1, al2))

    @classmethod
    def columnize(cls, ptups):
        rdname_1, rdname_2 = [], []
        rdlen_1, rdlen_2 = [], []
        best1_1, best1_2 = [], []
        best2_1, best2_2 = [], []
        minv_1, maxv_1, minv_2, maxv_2 = [], [], [], []
        mapq_1, mapq_2 = [], []
        best1conc, best2conc = [], []
        fraglen = []
        for ptup in ptups:
            rdname_1.append(ptup.rdname1)
            rdname_2.append(ptup.rdname2)
            best1_1.append(ptup.bestsc1)
            best1_2.append(ptup.bestsc2)
            best2_1.append(ptup.best2sc1)
            best2_2.append(ptup.best2sc2)
            rdlen_1.append(ptup.rdlen1)
            rdlen_2.append(ptup.rdlen2)
            mapq_1.append(ptup.mapq1)
            mapq_2.append(ptup.mapq2)
            best1conc.append(ptup.bestconcsc)
            best2conc.append(ptup.best2concsc)
            minv_1.append(ptup.minv1)
            minv_2.append(ptup.minv2)
            maxv_1.append(ptup.maxv1)
            maxv_2.append(ptup.maxv2)
            fraglen.append(ptup.fraglen)
        return rdname_1, best1_1, best2_1, minv_1, maxv_1, rdlen_1, mapq_1,\
            rdname_2, best1_2, best2_2, minv_2, maxv_2, rdlen_2, mapq_2,\
            best1conc, best2conc, fraglen

    @classmethod
    def to_data_frames(cls, ptups, cor=None):
        """ Convert the paired-end tuples to a pandas DataFrame """
        from pandas import DataFrame
        rdname_1, best1_1, best2_1, minv_1, maxv_1, rdlen_1, mapq_1,\
            rdname_2, best1_2, best2_2, minv_2, maxv_2, rdlen_2, mapq_2,\
            best1conc, best2conc, fraglen = PairedTuple.columnize(ptups)
        df = DataFrame.from_items([('name_1', rdname_1),
                                   ('best1_1', best1_1),
                                   ('best2_1', best2_1),
                                   ('minv_1', minv_1),
                                   ('maxv_1', maxv_1),
                                   ('rdlen_1', rdlen_1),
                                   ('mapq_1', mapq_1),
                                   ('name_2', rdname_2),
                                   ('best1_2', best1_2),
                                   ('best2_2', best2_2),
                                   ('minv_2', minv_2),
                                   ('maxv_2', maxv_2),
                                   ('rdlen_2', rdlen_2),
                                   ('mapq_2', mapq_2),
                                   ('best1conc', best1conc),
                                   ('best2conc', best2conc),
                                   ('fraglen', fraglen)])
        if cor is not None:
            df['correct'] = cor
        return df


class Dataset(object):
    
    """ Encapsulates a collection of training or test data.  Training data is
        labeled, test data not.  Right now this is being stored row-wise.
        This works well for saving and loading the rows to/from a CSV file.
        But it doesn't work so well for other things we'd like to do, like
        rescaling. """
    
    def __init__(self):
        # Data for individual reads and mates.  Tuples are (rdlen, minValid,
        # maxValid, bestSc, scDiff)
        self.data_unp, self.lab_unp = [], []
        # Data for concordant pairs.  Tuples are two tuples as described above,
        # one for each mate, plus the fragment length.  Label says whether the
        # first mate's alignment is correct.
        self.data_conc, self.lab_conc = [], []
        # Data for discordant pairs.
        self.data_disc, self.lab_disc = [], []
        # Data for bad ends
        self.data_bad_end, self.lab_bad_end = [], []

    def __len__(self):
        """ Return number of alignments added so far """
        return len(self.data_unp) + len(self.data_conc) + len(self.data_disc) + len(self.data_bad_end)
    
    def add_concordant(self, al1, al2, correct1, correct2):
        """ Add a concordant paired-end alignment to our dataset. """
        assert al1.concordant and al2.concordant
        rec1 = PairedTuple.from_alignments(al1, al2)
        rec2 = PairedTuple.from_alignments(al2, al1)
        for rec in [rec1, rec2]:
            self.data_conc.append(rec)
        self.lab_conc.extend([correct1, correct2])

    def add_discordant(self, al1, al2, correct1, correct2):
        """ Add a discordant paired-end alignment to our dataset. """
        assert al1.discordant and al2.discordant
        rec1 = PairedTuple.from_alignments(al1, al2)
        rec2 = PairedTuple.from_alignments(al2, al1)
        for rec in [rec1, rec2]:
            self.data_disc.append(rec)
        self.lab_disc.extend([correct1, correct2])

    def add_bad_end(self, al, unaligned, correct):
        """ Add a discordant paired-end alignment to our dataset. """
        assert al.paired
        self.data_bad_end.append(UnpairedTuple.from_alignment(al, len(unaligned.seq)))
        self.lab_bad_end.append(correct)

    def add_unpaired(self, al, correct):
        """ Add an alignment for a simulated unpaired read to our dataset. """
        self.data_unp.append(UnpairedTuple.from_alignment(al))
        self.lab_unp.append(correct)

    def save(self, fnprefix, compress=True):
        """ Save a file that we can load from R using read.csv with
            default arguments """
        fnmap = {'_unp': (self.data_unp, self.lab_unp, False),
                 '_conc': (self.data_conc, self.lab_conc, True),
                 '_disc': (self.data_disc, self.lab_disc, True),
                 '_bad_end': (self.data_bad_end, self.lab_bad_end, False)}
        for lab, p in fnmap.iteritems():
            data, corrects, paired = p
            fn = fnprefix + lab + '.csv'
            if compress:
                import gzip
                fh = gzip.open(fn + '.gz', 'w')
            else:
                fh = open(fn, 'w')
            if paired:
                fh.write(','.join(['name1', 'best1', 'secbest1', 'minv1', 'maxv1', 'len1', 'mapq1',
                                   'name2', 'best2', 'secbest2', 'minv2', 'maxv2', 'len2', 'mapq2',
                                   'bestconc', 'secbestconc', 'fraglen', 'correct']) + '\n')
            else:
                fh.write(','.join(['name', 'best', 'secbest', 'minv', 'maxv', 'len', 'mapq',
                                   'olen', 'correct']) + '\n')
            for tup, correct in izip(data, corrects):
                correct_str = 'NA'
                if correct is not None:
                    correct_str = 'T' if correct else 'F'
                tup = map(lambda x: 'NA' if x is None else str(x), tup)
                tup.append(correct_str)
                fh.write(','.join(tup) + '\n')
            fh.close()

    def load(self, fnprefix):
        fnmap = {'_unp': (self.data_unp, self.lab_unp, False),
                 '_conc': (self.data_conc, self.lab_conc, True),
                 '_disc': (self.data_disc, self.lab_disc, True),
                 '_bad_end': (self.data_bad_end, self.lab_bad_end, False)}
        for lab, p in fnmap.iteritems():
            data, corrects, paired = p
            fn = fnprefix + lab + '.csv'
            if os.path.exists(fn + '.gz'):
                import gzip
                fh = gzip.open(fn + '.gz')
            else:
                fh = open(fn)

            def int_or_none(s):
                return None if s == 'NA' else int(s)

            if paired:
                for toks in csv.reader(fh):
                    assert 18 == len(toks)
                    if 'name1' == toks[0]:
                        continue  # skip header
                    # Note: pandas csv parser is much faster
                    rdname1, best1, secbest1, minv1, maxv1, ln1, mapq1 = map(int_or_none, toks[0:7])
                    rdname2, best2, secbest2, minv2, maxv2, ln2, mapq2 = map(int_or_none, toks[7:14])
                    bestconc, secbestconc, fraglen = map(int_or_none, toks[14:17])
                    data.append(PairedTuple(rdname1, ln1, minv1, maxv1, best1, secbest1, mapq1,
                                            rdname2, ln2, minv2, maxv2, best2, secbest2, mapq2,
                                            bestconc, secbestconc, fraglen))
                    corrects.append(toks[-1] == 'T')
            else:
                for toks in csv.reader(fh):
                    assert 8 == len(toks)
                    if 'name' == toks[0]:
                        continue  # skip header
                    # Note: pandas csv parser is much faster
                    rdname, best, secbest, minv, maxv, ln, mapq, oln = map(int_or_none, toks[:8])
                    data.append(UnpairedTuple(rdname, ln, minv, maxv, best, secbest, mapq, oln))
                    corrects.append(toks[-1] == 'T')
            fh.close()

    def to_data_frames(self):
        """ Convert dataset to tuple of 3 pandas DataFrames. """
        return (UnpairedTuple.to_data_frame(self.data_unp, self.lab_unp),
                PairedTuple.to_data_frames(self.data_conc, self.lab_conc),
                PairedTuple.to_data_frames(self.data_disc, self.lab_disc),
                UnpairedTuple.to_data_frames(self.data_bad_end, self.lab_bad_end))
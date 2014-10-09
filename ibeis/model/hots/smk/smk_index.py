"""
smk_index
This module contains functions for the SelectiveMatchKernels's inverted index.

TODO::
    * Test suit 1000k images
    * Extend for SMK with labels
    * Test get numbers and refine
    * Extrnal keypoint specific weighting
"""
from __future__ import absolute_import, division, print_function
#import six
import utool
import numpy as np
#import pandas as pd
from six.moves import zip, map  # NOQA
from vtool import clustering2 as clustertool
from vtool import nearest_neighbors as nntool
from ibeis.model.hots.smk import smk_core
from ibeis.model.hots.smk import smk_speed
#from ibeis.model.hots.smk import smk_match
#from ibeis.model.hots.smk import pandas_helpers as pdh
from ibeis.model.hots.smk.hstypes import INTEGER_TYPE, FLOAT_TYPE, INDEX_TYPE
#from ibeis.model.hots.smk.pandas_helpers import VEC_COLUMNS, KPT_COLUMNS
from collections import namedtuple
(print, print_, printDBG, rrr, profile) = utool.inject(__name__, '[smk_index]')

USE_CACHE_WORDS = not utool.get_argflag('--nocache-words')
WITH_TOTALTIME = False


#@six.add_metaclass(utool.ReloadingMetaclass)
class InvertedIndex(object):
    """
    Stores inverted index state information
    (mapping from words to database aids and fxs_list)

    Attributes:
        idx2_dvec    (ndarray): stacked index -> descriptor vector (currently sift)
        idx2_daid    (ndarray): stacked index -> annot id
        idx2_dfx     (ndarray): stacked index -> feature index (wrt daid)
        idx2_fweight (ndarray): stacked index -> feature weight
        words        (ndarray): visual word centroids
        wordflann    (FLANN): FLANN search structure
        wx2_idxs     (ndarray): word index -> stacked indexes
        wx2_aids     (ndarray): word index -> aggregate aids
        wx2_fxs      (ndarray): word index -> aggregate feature indexes
        wx2_maws     (ndarray): word index -> multi-assign weights
        wx2_drvecs   (ndarray): word index -> residual vectors
        wx2_idf      (ndarray): word index -> idf (wx normalizer)
        daids        (ndarray): indexed annotation ids
        daid2_sccw   (ndarray): daid -> sccw (daid self-consistency weight)
        daid2_label  (ndarray): daid -> label (name, view)

    """
    def __init__(invindex, words, wordflann, idx2_vec, idx2_aid, idx2_fx,
                 daids, daid2_label):
        invindex.words        = words
        invindex.wordflann    = wordflann
        invindex.idx2_dvec    = idx2_vec
        invindex.idx2_daid    = idx2_aid
        invindex.idx2_dfx     = idx2_fx
        invindex.daids        = daids
        invindex.daid2_label  = daid2_label
        invindex.wx2_idxs     = None
        invindex.wx2_aids     = None
        invindex.wx2_fxs      = None
        invindex.wx2_maws     = None
        invindex.wx2_drvecs   = None
        invindex.wx2_idf      = None
        invindex.daid2_sccw   = None
        invindex.idx2_fweight = None


QueryIndex = namedtuple(
    'QueryIndex', (
        'wx2_qrvecs',
        'wx2_maws',
        'wx2_qaids',
        'wx2_qfxs',
        'query_sccw',
    ))


def lazy_getter(getter_func):
    def lazy_closure(*args):
        return getter_func(*args)
    return lazy_closure


def get_annot_label(ibs, aid_list):
    name_list = ibs.get_annot_nids(aid_list)
    view_list = [0 for _ in name_list]
    label_list = list(zip(name_list, view_list))
    return label_list


class DataFrameProxy(object):
    def __init__(self, ibs):
        self.ibs = ibs

    def __getitem__(self, key):
        if key == 'kpts':
            return lazy_getter(self.ibs.get_annot_kpts)
        elif key == 'vecs':
            return lazy_getter(self.ibs.get_annot_desc)
        elif key == 'labels':
            import functools
            return lazy_getter(functools.partial(get_annot_label, self.ibs))


#@profile
def make_annot_df(ibs):
    """
    Creates a panda dataframe using an ibeis controller

    Example:
        >>> from ibeis.model.hots.smk.smk_index import *  # NOQA
        >>> from ibeis.model.hots.smk import smk_debug
        >>> ibs = smk_debug.testdata_ibeis()
        >>> annots_df = make_annot_df(ibs)
        >>> print(utool.hashstr(repr(annots_df.values)))
        j12n+x93m4c!4un3

    #>>> from ibeis.model.hots.smk import smk_debug
    #>>> smk_debug.rrr()
    #>>> smk_debug.check_dtype(annots_df)
    """
    #aid_list = ibs.get_valid_aids()  # 80us
    annots_df = DataFrameProxy(ibs)
    #kpts_list = ibs.get_annot_kpts(aid_list)  # 40ms
    #vecs_list = ibs.get_annot_desc(aid_list)  # 50ms
    #assert len(kpts_list) == len(vecs_list)
    #assert len(label_list) == len(vecs_list)
    #aid_series = pdh.IntSeries(np.array(aid_list, dtype=INTEGER_TYPE), name='aid')
    #label_series = pd.Series(label_list, index=aid_list, name='labels')
    #kpts_df = pdh.pandasify_list2d(kpts_list, aid_series, KPT_COLUMNS, 'fx', 'kpts')  # 6.7ms
    #vecs_df = pdh.pandasify_list2d(vecs_list, aid_series, VEC_COLUMNS, 'fx', 'vecs')  # 7.1ms
    ## Pandas Annotation Dataframe
    #annots_df = pd.concat([kpts_df, vecs_df, label_series], axis=1)  # 845 us
    return annots_df


#@profile
def learn_visual_words(annots_df, taids, nWords, use_cache=USE_CACHE_WORDS):
    """
    Computes and caches visual words

    Example:
        >>> from ibeis.model.hots.smk.smk_index import *  # NOQA
        >>> from ibeis.model.hots.smk import smk_debug
        >>> ibs, annots_df, taids, daids, qaids, nWords = smk_debug.testdata_dataframe()
        >>> use_cache = True
        >>> words = learn_visual_words(annots_df, taids, nWords)
        >>> print(words.shape)
        (8000, 128)
    """
    max_iters = 200
    flann_params = {}
    #train_vecs_list = [pdh.ensure_values(vecs) for vecs in annots_df['vecs'][taids].values]
    train_vecs_list = annots_df['vecs'](taids)
    train_vecs = np.vstack(train_vecs_list)
    print('Training %d word vocabulary with %d annots and %d descriptors' %
          (nWords, len(taids), len(train_vecs)))
    kwds = dict(max_iters=max_iters, use_cache=use_cache, appname='smk',
                flann_params=flann_params)
    words = clustertool.cached_akmeans(train_vecs, nWords, **kwds)
    return words


def index_data_annots(annots_df, daids, words, with_internals=True,
                      aggregate=False, alpha=3, thresh=0):
    """
    Builds the initial inverted index from a dataframe, daids, and words.
    Optionally builds the internals of the inverted structure

    Example:
        >>> from ibeis.model.hots.smk.smk_index import *  # NOQA
        >>> from ibeis.model.hots.smk import smk_debug
        >>> ibs, annots_df, daids, qaids, words = smk_debug.testdata_words()
        >>> with_internals = False
        >>> invindex = index_data_annots(annots_df, daids, words, with_internals)

    Ignore:
        #>>> print(utool.hashstr(repr(list(invindex.__dict__.values()))))
        #v8+i5i8+55j0swio
    """
    if utool.VERBOSE:
        print('[smk_index] index_data_annots')
    flann_params = {}
    _words = words
    #_words = pdh.ensure_values(words)
    #_daids = pdh.ensure_values(daids)
    #_vecs_list = pdh.ensure_2d_values(annots_df['vecs'][_daids])
    #_label_list = pdh.ensure_values(annots_df['labels'][_daids])
    wordflann = nntool.flann_cache(_words, flann_params=flann_params,
                                   appname='smk')
    _daids = daids
    _vecs_list = annots_df['vecs'](_daids)
    _label_list = annots_df['labels'](_daids)
    _idx2_dvec, _idx2_daid, _idx2_dfx = nntool.invertable_stack(_vecs_list, _daids)

    idx2_dfx   = _idx2_dfx
    idx2_daid  = _idx2_daid
    idx2_dvec  = _idx2_dvec
    daid2_label = dict(zip(_daids, _label_list))

    invindex = InvertedIndex(words, wordflann, idx2_dvec, idx2_daid, idx2_dfx,
                             daids, daid2_label)
    if with_internals:
        compute_data_internals_(invindex, aggregate, alpha, thresh)  # 99%
    return invindex


@profile
def compute_data_internals_(invindex, aggregate=False, alpha=3, thresh=0):
    """
    Builds each of the inverted index internals.

    Example:
        >>> from ibeis.model.hots.smk.smk_index import *  # NOQA
        >>> from ibeis.model.hots.smk import smk_debug
        >>> ibs, annots_df, daids, qaids, invindex = smk_debug.testdata_raw_internals0()
        >>> aggregate = ibs.cfg.query_cfg.smk_cfg.aggregate
        >>> alpha = ibs.cfg.query_cfg.smk_cfg.alpha
        >>> thresh = ibs.cfg.query_cfg.smk_cfg.thresh
        >>> compute_data_internals_(invindex, aggregate, alpha, thresh)

    Ignore:
        idx2_vec = idx2_dvec
        wx2_maws = _wx2_maws  # NOQA
    """
    # Get information
    idx2_vec  = invindex.idx2_dvec
    idx2_dfx  = invindex.idx2_dfx
    idx2_daid = invindex.idx2_daid
    daids     = invindex.daids
    wordflann = invindex.wordflann
    words     = invindex.words
    wx_series = np.arange(len(words))
    if utool.VERBOSE:
        print('[smk_index] compute_data_internals_')
        print('[smk_index] * len(daids) = %r' % (len(daids),))
        print('[smk_index] * len(words) = %r' % (len(words),))
        print('[smk_index] * len(idx2_vec) = %r' % (len(idx2_vec),))
        print('[smk_index] * aggregate = %r' % (aggregate,))
        print('[smk_index] * alpha = %r' % (alpha,))
        print('[smk_index] * thresh = %r' % (thresh,))
    # Database word assignments (perform single assignment on database side)
    wx2_idxs, _wx2_maws, idx2_wxs = assign_to_words_(wordflann, words, idx2_vec, nAssign=1)
    if utool.DEBUG2:
        assert len(idx2_wxs) == len(idx2_vec)
        assert len(wx2_idxs.keys()) == len(_wx2_maws.keys())
        assert len(wx2_idxs.keys()) <= len(words)
        try:
            assert len(wx2_idxs.keys()) == len(words)
        except AssertionError as ex:
            utool.printex(ex, iswarning=True)
    # Database word inverse-document-frequency (idf weights)
    wx2_idf = compute_word_idf_(
        wx_series, wx2_idxs, idx2_daid, daids)
    if utool.DEBUG2:
        assert len(wx2_idf) == len(wx2_idf.keys())
    # Compute (normalized) residual vectors and inverse mappings
    wx2_drvecs, wx2_aids, wx2_fxs, wx2_maws = compute_residuals_(
        words, wx2_idxs, _wx2_maws, idx2_vec, idx2_daid, idx2_dfx, aggregate,
        is_database=True)
    # Try to save some memory
    invindex.idx2_dvec = None
    del idx2_vec
    # Compute annotation normalization factor
    wx2_rvecs = wx2_drvecs  # NOQA
    daid2_sccw = compute_data_sccw_(idx2_daid, wx2_drvecs, wx2_aids, wx2_idf, wx2_maws, alpha, thresh)
    # Store information
    invindex.idx2_wxs    = idx2_wxs   # stacked index -> word indexes
    invindex.wx2_idxs    = wx2_idxs
    invindex.wx2_idf     = wx2_idf
    invindex.wx2_drvecs  = wx2_drvecs
    invindex.wx2_aids    = wx2_aids  # needed for asmk
    invindex.wx2_fxs     = wx2_fxs   # needed for asmk
    invindex.wx2_maws    = wx2_maws  # needed for awx2_mawssmk
    invindex.daid2_sccw  = daid2_sccw

    if utool.DEBUG2:
        from ibeis.model.hots.smk import smk_debug
        smk_debug.check_invindex_wx2(invindex)


@profile
def assign_to_words_(wordflann, words, idx2_vec, nAssign=1, massign_alpha=1.2, massign_sigma=80):
    """
    Assigns descriptor-vectors to nearest word.

    Returns:
        tuple: inverted index, multi-assigned weights, and forward index
        formated as::

            * wx2_idxs - word index   -> vector indexes
            * wx2_maws - word index   -> multi-assignment weights
            * idf2_wxs - vector index -> assigned word indexes

    Example:
        >>> from ibeis.model.hots.smk.smk_index import *  # NOQA
        >>> from ibeis.model.hots.smk import smk_debug
        >>> ibs, annots_df, daids, qaids, invindex = smk_debug.testdata_raw_internals0()
        >>> words  = invindex.words
        >>> wordflann = invindex.wordflann
        >>> idx2_vec  = invindex.idx2_dvec
        >>> nAssign = ibs.cfg.query_cfg.smk_cfg.nAssign
        >>> _dbargs = (wordflann, words, idx2_vec,  nAssign)
        >>> wx2_idxs, wx2_maws, idx2_wxs = assign_to_words_(*_dbargs)
    """
    if utool.VERBOSE:
        print('[smk_index] +--- Start Assign vecs to words.')
        print('[smk_index] * nAssign=%r' % nAssign)
        print('[smk_index] * sigma=%r' % massign_sigma)
        print('[smk_index] * alpha=%r' % massign_alpha)
    # Assign each vector to the nearest visual words
    assert nAssign > 0, 'cannot assign to 0 neighbors'
    _idx2_wx, _idx2_wdist = wordflann.nn_index(idx2_vec, nAssign)
    _idx2_wx.shape    = (idx2_vec.shape[0], nAssign)
    _idx2_wdist.shape = (idx2_vec.shape[0], nAssign)
    if nAssign > 1:
        idx2_wxs, idx2_maws = _compute_multiassign_weights(
            _idx2_wx, _idx2_wdist, massign_alpha, massign_sigma)
    else:
        idx2_wxs = _idx2_wx.tolist()
        idx2_maws = [[1.0]] * len(idx2_wxs)

    # Invert mapping -- Group by word indexes
    jagged_idxs = ([idx] * len(wxs) for idx, wxs in enumerate(idx2_wxs))
    wx_keys, groupxs = clustertool.jagged_group(idx2_wxs)
    idxs_list = clustertool.apply_jagged_grouping(jagged_idxs, groupxs)
    maws_list = clustertool.apply_jagged_grouping(idx2_maws, groupxs)
    wx2_idxs = dict(zip(wx_keys, idxs_list))
    wx2_maws = dict(zip(wx_keys, maws_list))
    if utool.VERBOSE:
        print('[smk_index] L___ End Assign vecs to words.')

    return wx2_idxs, wx2_maws, idx2_wxs


def _compute_multiassign_weights(_idx2_wx, _idx2_wdist, massign_alpha=1.2, massign_sigma=80):
    """
    Multi Assignment Filtering from Improving Bag of Features

    References:
        http://lear.inrialpes.fr/pubs/2010/JDS10a/jegou_improvingbof_preprint.pdf
    """
    thresh  = np.multiply(massign_alpha, (_idx2_wdist.T[0:1].T + .001 ))
    invalid = np.greater_equal(_idx2_wdist, thresh)
    # Weighting as in Lost in Quantization
    gauss_numer = -_idx2_wdist.astype(np.float64)
    gauss_denom = 2 * (massign_sigma ** 2)
    gauss_exp   = np.divide(gauss_numer, gauss_denom)
    unnorm_maw = np.exp(gauss_exp)
    # Mask invalid multiassignment weights
    masked_unorm_maw = np.ma.masked_array(unnorm_maw, mask=invalid)
    # Normalize multiassignment weights from 0 to 1
    masked_norm = masked_unorm_maw.sum(axis=1)[:, np.newaxis]
    masked_maw = np.divide(masked_unorm_maw, masked_norm)
    masked_wxs = np.ma.masked_array(_idx2_wx, mask=invalid)
    # Remove masked weights and word indexes
    idx2_wxs  = list(map(utool.filter_Nones, masked_wxs.tolist()))
    idx2_maws = list(map(utool.filter_Nones, masked_maw.tolist()))
    #with utool.EmbedOnException():
    if utool.DEBUG2:
        checksum = [sum(maws) for maws in idx2_maws]
        for x in np.where([not utool.almost_eq(val, 1) for val in checksum])[0]:
            print(checksum[x])
            print(_idx2_wx[x])
            print(masked_wxs[x])
            print(masked_maw[x])
            print(thresh[x])
            print(_idx2_wdist[x])
        #all([utool.almost_eq(x, 1) for x in checksum])
        assert all([utool.almost_eq(val, 1) for val in checksum]), 'weights did not break evenly'
    return idx2_wxs, idx2_maws


#@utool.cached_func('idf_', appname='smk', key_argx=[1, 2, 3])
@profile
def compute_word_idf_(wx_series, wx2_idxs, idx2_aid, daids, daid2_label=None):
    """
    Computes the inverse-document-frequency weighting for each word

    Example:
        >>> from ibeis.model.hots.smk.smk_index import *  # NOQA
        >>> from ibeis.model.hots.smk import smk_debug
        >>> ibs, annots_df, daids, qaids, invindex, wx2_idxs = smk_debug.testdata_raw_internals1()
        >>> wx_series = np.arange(len(invindex.words))
        >>> idx2_aid = invindex.idx2_daid
        >>> daid2_label = invindex.daid2_label
        >>> wx2_idf = compute_word_idf_(wx_series, wx2_idxs, idx2_aid, daids)
        >>> print(wx2_idf.shape)
        (8000,)

    Ignore:
        #>>> wx2_idxs = invindex.wx2_idxs
    """
    if utool.VERBOSE:
        print('[smk_index] +--- Start Compute IDF')
        mark, end_ = utool.log_progress('[smk_index] Word IDFs: ',
                                        len(wx_series), flushfreq=500,
                                        writefreq=50, with_totaltime=WITH_TOTALTIME)
    # idxs for each word
    idxs_list = [wx2_idxs[wx].astype(INDEX_TYPE)
                 if wx in wx2_idxs
                 else np.empty(0, dtype=INDEX_TYPE)
                 for wx in wx_series]
    # aids for each word
    aids_list = [idx2_aid.take(idxs)
                 if len(idxs) > 0
                 else np.empty(0, dtype=INDEX_TYPE)
                 for idxs in idxs_list]
    if daid2_label is not None:
        idf_list = compute_idf_label1(aids_list, daid2_label)
    else:
        idf_list = compute_idf_orig(aids_list, daids)
    if utool.VERBOSE:
        end_()
        print('[smk_index] L___ End Compute IDF')
    wx2_idf = dict(zip(wx_series, idf_list))
    return wx2_idf


def compute_idf_orig(aids_list, daids):
    """
    The standard idf measure
    """
    nTotalDocs = len(daids)
    # idf denominator
    nDocsWithWord_list = np.array([len(set(aids)) for aids in aids_list])
    # Typically for IDF, 1 is added to the denominator to prevent divide by 0
    # compute idf half of sccw-idf weighting
    idf_list = np.log(np.divide(nTotalDocs, np.add(nDocsWithWord_list, 1),
                                dtype=FLOAT_TYPE), dtype=FLOAT_TYPE)
    return idf_list


def compute_idf_label1(aids_list, daid2_label):
    """
    One of our idf extensions
    >>> from ibeis.model.hots.smk.smk_index import *  # NOQA
    >>> from ibeis.model.hots.smk import smk_debug
    >>> ibs, annots_df, daids, qaids, invindex, wx2_idxs = smk_debug.testdata_raw_internals1()
    >>> wx_series = np.arange(len(invindex.words))
    >>> idx2_aid = invindex.idx2_daid
    >>> daid2_label = invindex.daid2_label
    >>> idxs_list = [wx2_idxs[wx].astype(INDEX_TYPE)
    >>>              if wx in wx2_idxs
    >>>              else np.empty(0, dtype=INDEX_TYPE)
    >>>              for wx in wx_series]
    >>> # aids for each word
    >>> aids_list = [idx2_aid.take(idxs)
    >>>              if len(idxs) > 0
    >>>              else np.empty(0, dtype=INDEX_TYPE)
    >>>              for idxs in idxs_list]
    >>> wx2_idf = compute_word_idf_(wx_series, wx2_idxs, idx2_aid, daids)
    """
    nWords = len(aids_list)
    # Computes our novel label idf weight
    lblindex_list = np.array(utool.tuples_to_unique_scalars(daid2_label.values()))
    #daid2_lblindex = dict(zip(daid_list, lblindex_list))
    unique_lblindexes, groupxs = clustertool.group_indicies(lblindex_list)
    daid_list = np.array(daid2_label.keys())
    daids_list = [daid_list.take(xs) for xs in groupxs]
    daid2_wxs = utool.ddict(list)
    for wx, daids in enumerate(aids_list):
        for daid in daids:
            daid2_wxs[daid].append(wx)
    lblindex2_daids = list(zip(unique_lblindexes, daids_list))
    nLabels = len(unique_lblindexes)
    pcntLblsWithWord = np.zeros(nWords, np.float64)
    # Get num times word appears for eachlabel
    for lblindex, daids in lblindex2_daids:
        nWordsWithLabel = np.zeros(nWords)
        for daid in daids:
            wxs = daid2_wxs[daid]
            nWordsWithLabel[wxs] += 1
        pcntLblsWithWord += (1 - nWordsWithLabel.astype(np.float64) / len(daids))

    # Labels for each word
    idf_list = np.log(np.divide(nLabels, np.add(pcntLblsWithWord, 1),
                                dtype=FLOAT_TYPE), dtype=FLOAT_TYPE)
    return idf_list


def compute_idf_label2(aids_list, daid2_label):
    r"""
    Chuck's formulation of label-idf

    Math::
        p(n_i | c) = \sum_{\ell \in L : \ell=(n_i, v)} p(\ell | c)

        p(\ell | c) = \frac{p(c | \ell) p(\ell)}{p(c)}

        p(c) = \sum_{\ell' \in L} p(c | \ell') p(\ell')

        p(c | \ell) = \frac{\sum_{\X \in \DB_\ell} b(c, \X)}{\card{\DB_\ell}}
    """
    nWords = len(aids_list)
    # Computes our novel label idf weight
    # Translate tuples into scalars for efficiency
    lblindex_list = np.array(utool.tuples_to_unique_scalars(daid2_label.values()))

    #daid2_lblindex = dict(zip(daid_list, lblindex_list))
    unique_lblindexes, groupxs = clustertool.group_indicies(lblindex_list)
    daid_list = np.array(daid2_label.keys())
    daids_list = [daid_list.take(xs) for xs in groupxs]
    daid2_wxs = utool.ddict(list)
    for wx, daids in enumerate(aids_list):
        for daid in daids:
            daid2_wxs[daid].append(wx)
    lblindex2_daids = list(zip(unique_lblindexes, daids_list))
    nLabels = len(unique_lblindexes)
    pcntLblsWithWord = np.zeros(nWords, np.float64)
    # Get num times word appears for eachlabel
    for lblindex, daids in lblindex2_daids:
        nWordsWithLabel = np.zeros(nWords)
        for daid in daids:
            wxs = daid2_wxs[daid]
            nWordsWithLabel[wxs] += 1
        pcntLblsWithWord += (1 - nWordsWithLabel.astype(np.float64) / len(daids))

    # Labels for each word
    idf_list = np.log(np.divide(nLabels, np.add(pcntLblsWithWord, 1), dtype=FLOAT_TYPE), dtype=FLOAT_TYPE)
    return idf_list


#@utool.cached_func('residuals', appname='smk')
@profile
def compute_residuals_(words, wx2_idxs, wx2_maws, idx2_vec, idx2_aid, idx2_fx,
                       aggregate, is_database=False):
    """
    Computes residual vectors based on worwx2_fxs d assignments
    returns mapping from word index to a set of residual vectors

    Returns:
        tuple : (wx2_rvecs, wx2_aids, wx2_fxs) formatted as::
            * wx2_rvecs - [ ... [ rvec_i1, ...,  rvec_Mi ]_i ... ]
            * wx2_aids  - [ ... [  aid_i1, ...,   aid_Mi ]_i ... ]
            * wx2_fxs   - [ ... [[fxs]_i1, ..., [fxs]_Mi ]_i ... ]

        For every word::

            * list of aggvecs
            * For every aggvec:
                * one parent aid, if aggregate is False: assert isunique(aids)
                * list of parent fxs, if aggregate is True: assert len(fxs) == 1

    Example:
        >>> from ibeis.model.hots.smk.smk_index import *  # NOQA
        >>> from ibeis.model.hots.smk import smk_debug
        >>> ibs, annots_df, daids, qaids, invindex, wx2_idxs = smk_debug.testdata_raw_internals1()
        >>> words     = invindex.words
        >>> idx2_aid  = invindex.idx2_daid
        >>> idx2_fx   = invindex.idx2_dfx
        >>> idx2_vec  = invindex.idx2_dvec
        >>> aggregate = ibs.cfg.query_cfg.smk_cfg.aggregate
        >>> wx2_rvecs, wx2_aids, wx2_fxs, wx2_maws = compute_residuals_(words, wx2_idxs, wx2_maws, idx2_vec, idx2_aid, idx2_fx, aggregate)
    """
    wx_sublist = np.array(wx2_idxs.keys())  # pdh.ensure_index(wx2_idxs)
    # Build lists w.r.t. words

    idxs_list = [wx2_idxs[wx].astype(INDEX_TYPE) for wx in wx_sublist]
    aids_list = [idx2_aid.take(idxs) for idxs in idxs_list]
    if utool.DEBUG2:
        #assert np.all(np.diff(wx_sublist) == 1), 'not dense'
        assert all([len(a) == len(b) for a, b in zip(idxs_list, aids_list)]), 'bad alignment'
        assert idx2_vec.shape[0] == idx2_fx.shape[0]
        assert idx2_vec.shape[0] == idx2_aid.shape[0]
    # Prealloc output
    if utool.VERBOSE:
        from ibeis.model.hots.smk import smk_debug
        print('[smk_index] +--- Start Compute Residuals')
        print('[smk_index] Residual Vectors for %d words. aggregate=%r' %
              (len(wx2_idxs), aggregate,))
        #if is_database:
        # There is usually a problem if the database doesn't index into any words
        smk_debug.check_wx2_idxs(wx2_idxs, len(words))
    # Nonaggregated residuals
    words_list = [words[wx:wx + 1] for wx in wx_sublist]  # 1 ms
    vecs_list  = [idx2_vec.take(idxs, axis=0) for idxs in idxs_list]  # 5.3 ms
    rvecs_list = [smk_core.get_norm_rvecs(vecs, word)
                  for vecs, word in zip(vecs_list, words_list)]  # 103 ms
    if aggregate:
        (wx2_rvecs, wx2_aids, wx2_fxs, wx2_maws) = _aggregate_residuals(
            rvecs_list, idxs_list, aids_list, idx2_fx, wx_sublist, wx2_maws)
    else:
        # Hack non-aggregate residuals to have the same structure as aggregate
        # residuals for compatability: i.e. each rvec gets a list of fxs that
        # contributed to it, and for SMK this is a list of size 1
        fxs_list  = [[idx2_fx[idx:idx + 1] for idx in idxs]  for idxs in idxs_list]
        wx2_rvecs = dict(zip(wx_sublist, rvecs_list))
        wx2_aids  = dict(zip(wx_sublist, aids_list))
        wx2_fxs   = dict(zip(wx_sublist, fxs_list))
    if utool.DEBUG2:
        from ibeis.model.hots.smk import smk_debug
        smk_debug.check_wx2(words, wx2_rvecs, wx2_aids, wx2_fxs)
    if utool.VERBOSE:
        print('[smk_index] L___ End Compute Residuals')
    return wx2_rvecs, wx2_aids, wx2_fxs, wx2_maws


def _aggregate_residuals(rvecs_list, idxs_list, aids_list, idx2_fx, wx_sublist, wx2_maws):
    """ Aggregate over words of the same aid """
    maws_list = [wx2_maws[wx] for wx in wx_sublist]
    tup = smk_speed.compute_agg_rvecs(rvecs_list, idxs_list, aids_list, maws_list)
    (aggvecs_list, aggaids_list, aggidxs_list, aggmaws_list) = tup
    aggfxs_list = [[idx2_fx.take(idxs) for idxs in aggidxs]
                   for aggidxs in aggidxs_list]
    wx2_aggvecs = dict(zip(wx_sublist, aggvecs_list))
    wx2_aggaids = dict(zip(wx_sublist, aggaids_list))
    wx2_aggfxs  = dict(zip(wx_sublist, aggfxs_list))
    wx2_aggmaws = dict(zip(wx_sublist, aggmaws_list))
    # Alisas
    return (wx2_aggvecs, wx2_aggaids, wx2_aggfxs, wx2_aggmaws)


#@utool.cached_func('sccw', appname='smk', key_argx=[1, 2])
@profile
def compute_data_sccw_(idx2_daid, wx2_rvecs, wx2_aids, wx2_idf, wx2_maws, alpha, thresh):
    """
    Computes sccw normalization scalar for the database annotations.
    This is gamma from the SMK paper.
    sccw is a self consistency critiron weight --- a scalar which ensures
    the score of K(X, X) = 1

    Example:
        >>> from ibeis.model.hots.smk.smk_index import *  # NOQA
        >>> from ibeis.model.hots.smk import smk_debug
        >>> ibs, annots_df, invindex, wx2_idxs, wx2_idf, wx2_rvecs, wx2_aids = smk_debug.testdata_raw_internals2()
        >>> alpha = ibs.cfg.query_cfg.smk_cfg.alpha
        >>> thresh = ibs.cfg.query_cfg.smk_cfg.thresh
        >>> idx2_daid  = invindex.idx2_daid
        >>> wx2_idf = wx2_idf
        >>> daids      = invindex.daids
        >>> daid2_sccw = compute_data_sccw_(idx2_daid, wx2_rvecs, wx2_aids, wx2_idf, daids)
    """
    if utool.DEBUG2:
        from ibeis.model.hots.smk import smk_debug
        smk_debug.rrr()
        smk_debug.check_wx2(wx2_rvecs=wx2_rvecs, wx2_aids=wx2_aids)

    wx_sublist = np.array(wx2_rvecs.keys())
    if utool.VERBOSE:
        print('\n[smk_index] +--- Start Compute Data Self Consistency Weight')
        print('[smk_index] Compute SCCW alpha=%r, thresh=%r: ' % (alpha, thresh))
        mark1, end1_ = utool.log_progress(
            '[smk_index] SCCW group (by present words): ', len(wx_sublist),
            flushfreq=100, writefreq=50, with_totaltime=WITH_TOTALTIME)
    # Get list of aids and rvecs w.r.t. words
    aids_list   = [wx2_aids[wx] for wx in wx_sublist]
    rvecs_list1 = [wx2_rvecs[wx] for wx in wx_sublist]
    maws_list   = [wx2_maws[wx] for wx in wx_sublist]
    if utool.DEBUG2:
        from ibeis.model.hots.smk import smk_debug
        smk_debug.assert_single_assigned_maws(maws_list)
    # Group by daids first and then by word index
    daid2_wx2_drvecs = clustertool.double_group(wx_sublist, aids_list, rvecs_list1)

    if utool.VERBOSE:
        end1_()

    # For every daid, compute its sccw using pregrouped rvecs
    # Summation over words for each aid
    if utool.VERBOSE:
        mark2, end2_ = utool.log_progress(
            '[smk_index] SCCW Sum (over daid): ', len(daid2_wx2_drvecs),
            flushfreq=100, writefreq=25, with_totaltime=WITH_TOTALTIME)
    # Get lists w.r.t daids
    aid_list = list(daid2_wx2_drvecs.keys())
    # list of mappings from words to rvecs foreach daid
    # [wx2_aidrvecs_1, ..., wx2_aidrvecs_nDaids,]
    _wx2_aidrvecs_list = list(daid2_wx2_drvecs.values())
    _aidwxs_iter   = (list(wx2_aidrvecs.keys()) for wx2_aidrvecs in _wx2_aidrvecs_list)
    aidrvecs_list  = [list(wx2_aidrvecs.values()) for wx2_aidrvecs in _wx2_aidrvecs_list]
    aididf_list = [[wx2_idf[wx] for wx in aidwxs] for aidwxs in _aidwxs_iter]

    if utool.DEBUG2:
        from ibeis.model.hots.smk import smk_debug
        smk_debug.check_data_smksumm(aididf_list, aidrvecs_list)
    # TODO: implement database side soft-assign
    sccw_list = [smk_core.sccw_summation(rvecs_list, idf_list, None, alpha, thresh)
                     for idf_list, rvecs_list in zip(aididf_list, aidrvecs_list)]

    daid2_sccw = dict(zip(aid_list, sccw_list))
    if utool.VERBOSE:
        end2_()
        print('[smk_index] L___ End Compute Data SCCW\n')

    return daid2_sccw


@profile
def new_qindex(annots_df, qaid, invindex, aggregate=False, alpha=3,
                       thresh=0, nAssign=1):
    """
    Gets query read for computations

    Example:
        >>> from ibeis.model.hots.smk.smk_index import *  # NOQA
        >>> from ibeis.model.hots.smk import smk_debug
        >>> ibs, annots_df, qaid, invindex = smk_debug.testdata_query_repr()
        >>> aggregate = ibs.cfg.query_cfg.smk_cfg.aggregate
        >>> alpha     = ibs.cfg.query_cfg.smk_cfg.alpha
        >>> thresh    = ibs.cfg.query_cfg.smk_cfg.thresh
        >>> nAssign   = ibs.cfg.query_cfg.smk_cfg.nAssign
        >>> _args = (annots_df, qaid, invindex, aggregate, alpha, thresh, nAssign)
        >>> qindex = new_qindex(*_args)
        >>> (wx2_qrvecs, wx2_qmaws, wx2_qaids, wx2_qfxs, query_sccw) = qindex
        >>> assert smk_debug.check_wx2_rvecs(wx2_qrvecs), 'has nan'
        >>> invindex_dbgstr.invindex_dbgstr(invindex)

    Ignore::
        idx2_vec = qfx2_vec
        idx2_aid = qfx2_aid
        idx2_fx  = qfx2_qfx
        wx2_idxs = _wx2_qfxs
        wx2_maws = _wx2_maws
    """
    if utool.VERBOSE:
        print('[smk_index] Query Repr qaid=%r' % (qaid,))
    wx2_idf   = invindex.wx2_idf
    words     = invindex.words
    wordflann = invindex.wordflann
    #qfx2_vec  = annots_df['vecs'][qaid].values
    qfx2_vec  = annots_df['vecs'](qaid)
    # Assign query to (multiple) words
    _wx2_qfxs, _wx2_maws, qfx2_wxs = assign_to_words_(
        wordflann, words, qfx2_vec, nAssign=nAssign)
    # Hack to make implementing asmk easier, very redundant
    qfx2_aid = np.array([qaid] * len(qfx2_wxs), dtype=INTEGER_TYPE)
    qfx2_qfx = np.arange(len(qfx2_vec))
    # Compute query residuals
    wx2_qrvecs, wx2_qaids, wx2_qfxs, wx2_maws = compute_residuals_(
        words, _wx2_qfxs, _wx2_maws, qfx2_vec, qfx2_aid, qfx2_qfx, aggregate)
    # each value in wx2_ dicts is a list with len equal to the number of rvecs
    # Compute query sccw
    if utool.VERBOSE:
        print('[smk_index] Query SCCW alpha=%r, thresh=%r' % (alpha, thresh))
    wx_sublist  = np.array(wx2_qrvecs.keys(), dtype=INDEX_TYPE)
    idf_list    = [wx2_idf[wx]    for wx in wx_sublist]
    rvecs_list  = [wx2_qrvecs[wx] for wx in wx_sublist]
    maws_list   = [wx2_maws[wx]   for wx in wx_sublist]
    query_sccw = smk_core.sccw_summation(rvecs_list, idf_list, maws_list, alpha, thresh)
    assert query_sccw > 0, 'query sccw is not positive!'
    # Build query representationm class/tuple
    qindex = QueryIndex(wx2_qrvecs, wx2_maws, wx2_qaids, wx2_qfxs, query_sccw)
    return qindex
    #return wx2_qrvecs, wx2_qaids, wx2_qfxs, query_sccw

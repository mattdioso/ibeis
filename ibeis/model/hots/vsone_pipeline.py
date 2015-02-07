"""
special pipeline for vsone specific functions


Current Issues:
    * getting feature distinctiveness is too slow, we can either try a different
      model, or precompute feature distinctiveness.

      - we can reduce the size of the vsone shortlist

TODOLIST:
    * Precompute distinctivness
    * Paramatarize
     - grid / image coverage
     - image cov params
     - grid cov params
     - scr-vsone / rat-vsone
     - scr-params
     - rat-params

     - true-pos-score in qres
     - false-neg-score in qres
     - false-pos-score in qres

"""
from __future__ import absolute_import, division, print_function
import six
import numpy as np
import vtool as vt
#from ibeis.model.hots import neighbor_index
from ibeis.model.hots import name_scoring
from ibeis.model.hots import hstypes
#import pyflann
#from ibeis.model.hots import coverage_image
from vtool import coverage_image
from ibeis.model.hots import _pipeline_helpers as plh  # NOQA
from ibeis.model.hots import distinctiveness_normalizer
import utool as ut
from six.moves import zip, range  # NOQA
#profile = ut.profile
print, print_,  printDBG, rrr, profile = ut.inject(__name__, '[vsonepipe]', DEBUG=False)


#@profile
def vsone_reranking(qreq_, qaid2_chipmatch, verbose=False):
    """
    Driver function for vsone reranking

    CommandLine:
        python -m ibeis.model.hots.vsone_pipeline --test-vsone_reranking
        utprof.py -m ibeis.model.hots.vsone_pipeline --test-vsone_reranking
        python -m ibeis.model.hots.vsone_pipeline --test-vsone_reranking --show

    Example:
        >>> from ibeis.model.hots.vsone_pipeline import *  # NOQA
        >>> cfgdict = dict(dupvote_weight=1.0, prescore_method='nsum', score_method='nsum', sver_weighting=True)
        >>> ibs, qreq_ = plh.get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict, qaid_list=[1, 4, 6])
        >>> locals_ = plh.testrun_pipeline_upto(qreq_, 'chipmatch_to_resdict')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch_SVER']
        >>> qaid2_chipmatch_VSONE = vsone_reranking(qreq_, qaid2_chipmatch)
        >>> if ut.show_was_requested():
        >>>     import plottool as pt
        >>>     show_top_chipmatches(qreq_.ibs, qaid2_chipmatch_VSONE)
        >>>     pt.show_if_requested()

    Ignore:
        max_depth = None
        max_depth2 = 1
        print(ut.depth_profile(Hs_list, 0))
        print(ut.depth_profile(scores_list, max_depth))
        print(ut.depth_profile(daid_list, max_depth))
        print(ut.depth_profile(fms_list, max_depth2))
        print(ut.depth_profile(fsvs_list, max_depth))
    """
    # First find a shortlist to execute vsone reranking on
    qaid_list, daids_list, Hs_list = make_vsone_rerank_pairs(qreq_, qaid2_chipmatch)  # NOQA
    # Then execute vsone reranking
    vsone_res_tup = execute_vsone_reranking(qreq_, qaid_list, daids_list, Hs_list)
    # Format the output into chipmatches
    (daid_list, scores_list, fms_list, fsvs_list) = vsone_res_tup
    chipmatch_VSONE_list = []
    for daids, scores, fms, fsvs, Hs in zip(daid_list, scores_list, fms_list, fsvs_list, Hs_list):
        fks = [np.ones(len(fm), dtype=hstypes.FK_DTYPE) for fm in fms]
        aid2_fm    = dict(zip(daids, fms))
        aid2_fsv   = dict(zip(daids, fsvs))
        aid2_fk    = dict(zip(daids, fks))
        aid2_score = dict(zip(daids, scores))
        aid2_H     = dict(zip(daids, Hs))
        chipmatch_VSONE = hstypes.ChipMatch(aid2_fm, aid2_fsv, aid2_fk, aid2_score, aid2_H)
        chipmatch_VSONE_list.append(chipmatch_VSONE)
    qaid2_chipmatch_VSONE = dict(zip(qaid_list, chipmatch_VSONE_list))
    #qaid2_scores = dict(zip(qaid_list, scores_list))
    return qaid2_chipmatch_VSONE


@profile
def make_vsone_rerank_pairs(qreq_, qaid2_chipmatch):
    """
    Makes shortlists for vsone reranking

    CommandLine:
        python -m ibeis.model.hots.vsone_pipeline --test-make_vsone_rerank_pairs

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.vsone_pipeline import *  # NOQA
        >>> cfgdict = dict(dupvote_weight=1.0, prescore_method='nsum', score_method='nsum', sver_weighting=True)
        >>> ibs, qreq_ = plh.get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict)
        >>> locals_ = plh.testrun_pipeline_upto(qreq_, 'chipmatch_to_resdict')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch_SVER']
        >>> qaid = qreq_.get_external_qaids()[0]
        >>> chipmatch = qaid2_chipmatch[qaid]
        >>> qaid_list, top_aids_list, top_Hs_list = make_vsone_rerank_pairs(qreq_, qaid2_chipmatch)
        >>> top_aid_list = top_aids_list[0]
        >>> top_nid_list = ibs.get_annot_name_rowids(top_aid_list)
        >>> print('top_aid_list = %r' % (top_aid_list,))
        >>> print('top_nid_list = %r' % (top_nid_list,))
        >>> assert top_nid_list.index(1) == 0, 'name 1 should be rank 1'
        >>> assert len(top_nid_list) == 5, 'should have 3 names and up to 2 image per name'
    """
    from ibeis.model.hots import pipeline
    score_method = qreq_.qparams.score_method
    # TODO: paramaterize
    # Params: the max number of top names to get and the max number of
    # annotations per name to verify against
    nNameShortlistVsone = qreq_.qparams.nNameShortlistVsone
    nAnnotPerName       = qreq_.qparams.nAnnotPerName
    assert score_method == 'nsum'
    print('vsone reranking. ')
    qaid_list = list(six.iterkeys(qaid2_chipmatch))
    chipmatch_list = ut.dict_take(qaid2_chipmatch, qaid_list)
    daids_list = []
    Hs_list = []
    ibs = qreq_.ibs
    for qaid, chipmatch in zip(qaid_list, chipmatch_list):
        daid2_prescore = pipeline.score_chipmatch(qreq_, qaid, chipmatch, score_method)
        daid_list      = np.array(daid2_prescore.keys())
        prescore_arr   = np.array(daid2_prescore.values())
        # HACK POPULATE AID2_SCORE FIELD IN CHIPMATCH TUPLE
        ut.dict_assign(chipmatch.aid2_score, daid_list, prescore_arr)
        #
        nscore_tup = name_scoring.group_scores_by_name(ibs, daid_list, prescore_arr)
        (sorted_nids, sorted_nscore, sorted_aids, sorted_scores) = nscore_tup
        top_aids_list  = ut.listclip(sorted_aids, nNameShortlistVsone)
        top_aids_list_ = [ut.listclip(aids, nAnnotPerName) for aids in top_aids_list]  # ut.partialmap?
        top_aid_list = ut.flatten(top_aids_list_)
        top_H_list   = ut.dict_take(chipmatch.aid2_H, top_aid_list)
        # append shortlist results for this query aid
        daids_list.append(top_aid_list)
        Hs_list.append(top_H_list)
    return qaid_list, daids_list, Hs_list


#@profile
def execute_vsone_reranking(qreq_, qaid_list, daids_list_, Hs_list):
    r""" runs several pairs of (qaid, daids) vsone matches """
    ibs = qreq_.ibs
    # For each qaid, daids pair in the lists, execute a query
    vsone_iter = zip(qaid_list, daids_list_, Hs_list)
    progkw = dict(lbl='VSONE RERANKING', freq=1)
    vsone_prog_iter = ut.ProgressIter(vsone_iter, nTotal=len(qaid_list), **progkw)
    config = qreq_.qparams
    daid_score_fm_fsv_tup_list = [
        single_vsone_query(ibs, qaid, daid_list, H_list, config)
        for (qaid, daid_list, H_list) in vsone_prog_iter
    ]
    # Unpack results into their respective types
    daids_list   = ut.get_list_column(daid_score_fm_fsv_tup_list, 0)
    scores_list  = ut.get_list_column(daid_score_fm_fsv_tup_list, 1)
    fms_list     = ut.get_list_column(daid_score_fm_fsv_tup_list, 2)
    fsvs_list    = ut.get_list_column(daid_score_fm_fsv_tup_list, 3)
    vsone_res_tup = (daids_list, scores_list, fms_list, fsvs_list)
    return vsone_res_tup


@profile
def single_vsone_query(ibs, qaid, daid_list, H_list, config={}):
    r"""
    Args:
        ibs (IBEISController):  ibeis controller object
        qaid (int):  query annotation id
        daid_list (list):
        H_list (list):

    CommandLine:
        python -m ibeis.model.hots.vsone_pipeline --test-single_vsone_query

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.model.hots.vsone_pipeline import *  # NOQA
        >>> import ibeis
        >>> # build test data
        >>> ibs = ibeis.opendb('testdb1')
        >>> qaid = 1
        >>> daid_list = [3, 2, 5, 4]
        >>> H_list = [
        ...  np.array([[ -4.68815126e-01,   7.80306795e-02,  -2.23674587e+01],
        ...            [  4.54394231e-02,  -7.67438835e-01,   5.92158624e+01],
        ...            [  2.12918867e-04,  -8.64851418e-05,  -6.21472492e-01]]),
        ...  np.array([[  5.11319128e-01,  -2.69211436e-04,  -3.18079183e+01],
        ...            [ -5.97449121e-02,   4.67044573e-01,   5.27655556e+01],
        ...            [  1.06650025e-04,   8.70310639e-05,   5.28664052e-01]]),
        ...  np.array([[  4.47902439e-01,  -1.79874835e-01,  -1.88314836e-01],
        ...            [ -2.61825221e-02,   3.59390616e-01,   6.47754036e+01],
        ...            [ -1.02783595e-04,  -5.74416869e-04,   6.88664085e-01]]),
        ...  np.array([[  4.94544421e-01,   2.05268712e-01,  -5.35167763e+01],
        ...            [ -1.99183336e-01,   7.97940559e-01,  -2.45807386e+01],
        ...            [ -4.60593287e-04,   1.36874405e-03,   3.83659263e-01]])]
        >>> #species = ibeis.const.Species.ZEB_PLAIN
        >>> #dstncvs_normer = distinctiveness_normalizer.request_species_distinctiveness_normalizer(species)
        >>> # execute function
        >>> daid_fm_fs_score_tup = single_vsone_query(ibs, qaid, daid_list, H_list)
        >>> daid_list, fm_list, fs_list, score_list = daid_fm_fs_score_tup
        >>> print(score_list)

    Ignore:
        from ibeis.viz import viz_sver
        import plottool as pt

        next_pnum = pt.make_pnum_nextgen(*pt.get_square_row_cols(len(daid_list)))
        for fm, daid, H in zip(fm_SCR_list, daid_list, H_list):
            viz_sver.show_constrained_match(ibs, qaid, daid, H, fm, pnum=next_pnum())
        pt.update()
    """
    from ibeis.model.hots import name_scoring
    #print('==================')
    fm_list, fs_list = compute_query_matches(ibs, qaid, daid_list, H_list, config=config)  # 35.8
    # BIG MEMORY JUMP HERE
    #cov_score_list = compute_image_coverage_score(ibs, qaid, daid_list, fm_list, fs_list)  # 64.2
    cov_score_list = compute_grid_coverage_score(ibs, qaid, daid_list, fm_list, fs_list, config=config)  # 64.2
    NAME_SCORING = True
    if NAME_SCORING:
        # Keep only the best annotation per name
        nscore_tup = name_scoring.group_scores_by_name(ibs, daid_list, cov_score_list)
        score_list = ut.flatten([scores[0:1].tolist() + ([0] * (len(scores) - 1))
                                 for scores in nscore_tup.sorted_scores])
    else:
        score_list = cov_score_list
    # Convert our one score to a score vector here
    num_matches_iter = map(len, fm_list)
    num_filts = 1  # currently only using one vector here.
    fsv_list = [fs.reshape((num_matches, num_filts))
                for fs, num_matches in zip(fs_list, num_matches_iter)]
    daid_score_fm_fsv_tup = (daid_list, score_list, fm_list, fsv_list)
    return daid_score_fm_fsv_tup


@profile
def compute_query_matches(ibs, qaid, daid_list, H_list, config={}):
    r""" calls specified vsone matching routine for single (qaid, daids) pair """
    # TODO: implement unconstrained regular vsone
    fm_list, fs_list = compute_query_constrained_matches(ibs, qaid, daid_list, H_list, config)
    return fm_list, fs_list


@profile
def compute_query_constrained_matches(ibs, qaid, daid_list, H_list, config):
    flann_params = {
        'algorithm': 'kdtree',
        'trees': 8
    }
    match_xy_thresh = config.get('scr_xy_thresh', .05)
    ratio_thresh2   = config.get('scr_ratio_thresh', .7)
    normalizer_mode = config.get('scr_normalizer_mode', 'far')
    K               = config.get('scr_K', 7)
    qvecs = ibs.get_annot_vecs(qaid)
    qkpts = ibs.get_annot_kpts(qaid)
    flann_cachedir = ibs.get_flann_cachedir()
    use_cache = save = ut.is_developer()
    flann = vt.flann_cache(qvecs, flann_cachedir, flann_params=flann_params,
                           quiet=True, verbose=False, use_cache=use_cache, save=save)
    fm_SCR_list = []
    fs_SCR_list = []
    dvecs_list = ibs.get_annot_vecs(daid_list)
    dkpts_list = ibs.get_annot_kpts(daid_list)
    dfgws_list = ibs.get_annot_fgweights(daid_list)
    dlen_sqrd_list = ibs.get_annot_chip_dlen_sqrd(daid_list)
    dinfo_list = zip(dvecs_list, dkpts_list, dfgws_list, dlen_sqrd_list, H_list)
    for daid, dinfo in zip(daid_list, dinfo_list):
        # THIS CAN BE SWAPED WITH PURE RATIO TEST
        # ALSO, SVER CAN BE ADDED ON THE END
        dvecs, dkpts, dfgws, dlen_sqrd, H = dinfo
        fm_SCR, fs_SCR = spatially_constrained_match(
            flann, dvecs, qkpts, dkpts, H, dlen_sqrd, match_xy_thresh,
            ratio_thresh2, K, normalizer_mode)
        fm_SCR_list.append(fm_SCR)
        fs_SCR_list.append(fs_SCR)
    del flann
    #print('---------------- ;)(')
    return fm_SCR_list, fs_SCR_list


@profile
#@ut.memprof
def compute_image_coverage_score(ibs, qaid, daid_list, fm_list, fs_list, config={}):
    """
    Returns a grayscale chip match which represents which pixels
    should be matches in order for a candidate to be considered a match.

    CommandLine:
        python -m ibeis.model.hots.vsone_pipeline --test-compute_image_coverage_score

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.model.hots.vsone_pipeline import *  # NOQA
        >>> # build test data
        >>> ibs, qaid, daid_list, fm_list, fs_list = testdata_scoring()
        >>> # execute function
        >>> score_list = compute_image_coverage_score(ibs, qaid, daid_list, fm_list, fs_list)
        >>> # verify results
        >>> result = str(score_list)
        >>> print(result)

    Ignore:
        import plottool as pt
        pt.imshow(weight_mask * 255, update=True, fnum=2)
        pt.imshow(weight_mask_m * 255, update=True, fnum=3)
        pt.imshow(weight_color * 255, update=True, fnum=3)
    """
    # Distinctivness Weight
    #  Hits     Time     Per Hit    %Time
    #     3      7213349 2404449.7     28.6
    qdstncvs  = get_kpts_distinctiveness(ibs, [qaid], config=config)[0]
    #  Hits     Time     Per Hit    %Time
    #     3     14567165 4855721.7     57.8
    ddstncvs_list  = get_kpts_distinctiveness(ibs, daid_list, config=config)
    # Foreground weight
    qfgweight = ibs.get_annot_fgweights([qaid], ensure=True)[0]
    dfgweight_list = ibs.get_annot_fgweights(daid_list, ensure=True)
    # Make weight mask
    qchipsize = ibs.get_annot_chipsizes(qaid)
    qkpts     = ibs.get_annot_kpts(qaid)
    mode = 'max'
    # Foregroundness*Distinctiveness weight mask
    weights = (qfgweight * qdstncvs) ** .5
    #  Hits     Time     Per Hit    %Time
    #    3      2298873 766291.0      9.1
    print('==--==--==--==--==--==')
    weight_mask, patch = coverage_image.make_coverage_mask(
        qkpts, qchipsize, fx2_score=weights, mode=mode, resize=False)  # 9% of the time
    # Apply weighted scoring to matches
    score_list = []
    for fm, fs, ddstncvs, dfgweight in zip(fm_list, fs_list, ddstncvs_list, dfgweight_list):
        # Get matching query keypoints
        qkpts_m     = qkpts.take(fm.T[0], axis=0)
        ddstncvs_m  = ddstncvs.take(fm.T[1], axis=0)
        dfgweight_m = dfgweight.take(fm.T[1], axis=0)
        qdstncvs_m  = qdstncvs.take(fm.T[0], axis=0)
        qfgweight_m = qfgweight.take(fm.T[0], axis=0)
        weights_m = fs * np.sqrt(qdstncvs_m * ddstncvs_m) * np.sqrt(qfgweight_m * dfgweight_m)
        # Hits     Time     Per Hit    %Time
        #  46      1000214  21743.8      4.0
        weight_mask_m, patch = coverage_image.make_coverage_mask(
            qkpts_m, qchipsize, fx2_score=weights_m, mode=mode, resize=False)  # 4% of the time
        #if True:
        #    stacktup = (weight_mask, np.zeros(weight_mask.shape), weight_mask_m)
        #    weight_color = np.dstack(stacktup)
        coverage_score = weight_mask_m.sum() / weight_mask.sum()
        del weights_m
        del weight_mask_m
        score_list.append(coverage_score)
    del weight_mask
    return score_list


@profile
def compute_grid_coverage_score(ibs, qaid, daid_list, fm_list, fs_list, config={}):
    """

    CommandLine:
        python -m ibeis.model.hots.vsone_pipeline --test-compute_grid_coverage_score

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.model.hots.vsone_pipeline import *  # NOQA
        >>> # build test data
        >>> ibs, qaid, daid_list, fm_list, fs_list = testdata_scoring()
        >>> score_list = compute_grid_coverage_score(ibs, qaid, daid_list, fm_list, fs_list)
        >>> print(score_list)
    """
    qdstncvs  = get_kpts_distinctiveness(ibs, [qaid], config)[0]
    ddstncvs_list  = get_kpts_distinctiveness(ibs, daid_list, config)
    # Foreground weight
    qfgweight = ibs.get_annot_fgweights([qaid], ensure=True)[0]
    dfgweight_list = ibs.get_annot_fgweights(daid_list, ensure=True)
    # Make weight mask
    chipsize = qchipsize = ibs.get_annot_chipsizes(qaid)  # NOQA
    kpts = qkpts = ibs.get_annot_kpts(qaid)  # NOQA
    #mode = 'max'
    # Foregroundness*Distinctiveness weight mask
    weights = (qfgweight * qdstncvs) ** .5
    gridcfg = dict(
        resize=False,
        grid_scale_factor=config.get('grid_scale_factor', .2),
        grid_steps=config.get('grid_steps', 2),
    )
    #exec(ut.util_dbg.execstr_dict(gridcfg), globals(), locals())
    # 100 loops, best of 3: 10.9 ms per loop
    weight_mask = coverage_image.get_grid_coverage_mask(kpts, chipsize, weights, **gridcfg)
    # Prealloc data for loop
    weight_mask_m = weight_mask.copy()
    # Apply weighted scoring to matches
    score_list = []
    for fm, fs, ddstncvs, dfgweight in zip(fm_list, fs_list, ddstncvs_list, dfgweight_list):
        # Get matching query keypoints
        qkpts_m     = qkpts.take(fm.T[0], axis=0)
        ddstncvs_m  = ddstncvs.take(fm.T[1], axis=0)
        dfgweight_m = dfgweight.take(fm.T[1], axis=0)
        qdstncvs_m  = qdstncvs.take(fm.T[0], axis=0)
        qfgweight_m = qfgweight.take(fm.T[0], axis=0)
        weights_m = fs * np.sqrt(qdstncvs_m * ddstncvs_m) * np.sqrt(qfgweight_m * dfgweight_m)
        weight_mask_m = coverage_image.get_grid_coverage_mask(
            qkpts_m, chipsize, weights_m, out=weight_mask_m, **gridcfg)  # 4% of the time
        coverage_score = weight_mask_m.sum() / weight_mask.sum()
        score_list.append(coverage_score)
    return score_list


@profile
def spatially_constrained_match(flann, dvecs, qkpts, dkpts, H, dlen_sqrd,
                                match_xy_thresh, ratio_thresh2,  K, normalizer_mode):
    from vtool import constrained_matching
    # Find candidate matches matches
    #  Hits     Time     Per Hit    %Time
    #    46     13082250 284396.7     94.6
    dfx2_qfx, _dfx2_dist = flann.nn_index(dvecs, num_neighbors=K, checks=800)
    dfx2_dist = np.divide(_dfx2_dist, hstypes.VEC_PSEUDO_MAX_DISTANCE_SQRD)
    # Remove infeasible matches
    constraintup = constrained_matching.spatially_constrain_matches(
        dlen_sqrd, qkpts, dkpts, H, dfx2_qfx, dfx2_dist, match_xy_thresh,
        normalizer_mode=normalizer_mode)
    (fm_SC, fm_norm_SC, match_dist_list, norm_dist_list) = constraintup
    fs_SC = 1 - np.divide(match_dist_list, norm_dist_list)   # NOQA
    # Given matching distance and normalizing distance, filter by ratio scores
    fm_SCR, fs_SCR, fm_norm_SCR = constrained_matching.ratio_test2(
        match_dist_list, norm_dist_list, fm_SC, fm_norm_SC, ratio_thresh2)
    return fm_SCR, fs_SCR


@profile
def get_kpts_distinctiveness(ibs, aid_list, config={}):
    """
    per-species disinctivness wrapper around ibeis cached function
    """
    aid_list = np.array(aid_list)
    sid_list = np.array(ibs.get_annot_species_rowids(aid_list))
    # Compute distinctivness separately for each species
    unique_sids, groupxs = vt.group_indicies(sid_list)
    aids_groups = vt.apply_grouping(aid_list, groupxs)
    species_text_list = ibs.get_species_texts(unique_sids)
    # Map distinctivness computation
    normer_list = [distinctiveness_normalizer.request_species_distinctiveness_normalizer(species)
                   for species in species_text_list]

    dcvs_kw = {
        'dcvs_K'        : config.get('dcvs_K'),
        'dcvs_power'    : config.get('dcvs_power'),
        'dcvs_min_clip' : config.get('dcvs_min_clip'),
        'dcvs_max_clip' : config.get('dcvs_max_clip'),
    }

    # Reduce to get results
    dstncvs_groups = [
        # uses ibeis non-persistant cache
        # code lives in manual_ibeiscontrol_funcs
        ibs.get_annot_kpts_distinctiveness(aids, dstncvs_normer=dstncvs_normer, **dcvs_kw)
        for dstncvs_normer, aids in zip(normer_list, aids_groups)
    ]
    dstncvs_list = vt.invert_apply_grouping(dstncvs_groups, groupxs)
    return dstncvs_list


def testdata_scoring():
    import ibeis
    ibs = ibeis.opendb('testdb1')
    cfgdict = dict(dupvote_weight=1.0, prescore_method='nsum', score_method='nsum', sver_weighting=True)
    qaid = 1
    qaid_list = [qaid]
    # VSMANY TO GET HOMOG
    ibs, qreq_ = plh.get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict, qaid_list=qaid_list)
    locals_ = plh.testrun_pipeline_upto(qreq_, 'chipmatch_to_resdict')
    qaid2_chipmatch = locals_['qaid2_chipmatch_SVER']
    qaid_list, top_aids_list, top_Hs_list = make_vsone_rerank_pairs(qreq_, qaid2_chipmatch)
    qaid = qaid_list[0]
    daid_list = top_aids_list[0]
    H_list = top_Hs_list[0]
    # run vsone
    fm_list, fs_list = compute_query_matches(ibs, qaid, daid_list, H_list)  # 35.8
    return ibs, qaid, daid_list, fm_list, fs_list
    #qaid = qaid_list[0]
    #chipmatch = qaid2_chipmatch[qaid]
    #fm = chipmatch.aid2_fm[daid]
    #fsv = chipmatch.aid2_fsv[daid]


def show_top_chipmatches(ibs, qaid2_chipmatch, fnum_offset=0, figtitle=''):
    """ helper """
    from ibeis.viz import viz_sver
    import plottool as pt
    CLIP_TOP = 6
    for fnum_, (qaid, chipmatch) in enumerate(six.iteritems(qaid2_chipmatch)):
        fnum = fnum_ + fnum_offset
        #pt.figure(fnum=fnum, doclf=True, docla=True)
        daid_list = list(six.iterkeys(chipmatch.aid2_fm))
        score_list = ut.dict_take(chipmatch.aid2_score, daid_list)
        top_daid_list = ut.listclip(ut.sortedby(daid_list, score_list, reverse=True), CLIP_TOP)
        nRows, nCols = pt.get_square_row_cols(len(top_daid_list), fix=True)
        next_pnum = pt.make_pnum_nextgen(nRows, nCols)
        for daid in top_daid_list:
            fm = chipmatch.aid2_fm[daid]
            H = chipmatch.aid2_H[daid]
            score = chipmatch.aid2_score[daid]
            viz_sver.show_constrained_match(ibs, qaid, daid, H, fm, fnum=fnum, pnum=next_pnum())
            if ibs.get_match_truth(qaid, daid):
                pt.draw_border(pt.gca(), pt.TRUE_GREEN, 4)
            pt.set_title('score = %.3f' % (score,))
            #top_score_list = ut.dict_take(chipmatch.aid2_score, top_daid_list)
            #top_fm_list    = ut.dict_take(chipmatch.aid2_fm, top_daid_list)
            #top_fsv_list   = ut.dict_take(chipmatch.aid2_fsv, top_daid_list)
            #top_H_list     = ut.dict_take(chipmatch.aid2_H, top_daid_list)
        pt.set_figtitle('qaid=%r %s' % (qaid, figtitle))

    #vsone_query_pairs = make_vsone_rerank_pairs(qreq_, qaid2_chipmatch)
    #ibs = qreq_.ibs
    #for fnum, vsone_pair_tup in enumerate(vsone_query_pairs):
    #    (qaid, daid_list, H_list) = vsone_pair_tup
    #    nRows, nCols = pt.get_square_row_cols(len(daid_list))
    #    next_pnum = pt.make_pnum_nextgen(*daid_list)
    #    for daid in daid_list:
    #        fm = qaid2_chipmatch[qaid].aid2_fm[daid]
    #        H = qaid2_chipmatch[qaid].aid2_H[daid]
    #        viz_sver.show_constrained_match(ibs, qaid, daid, H, fm, pnum=next_pnum())


def show_annot_weights(ibs, aid, mode='dstncvs'):
    r"""
    DEMO FUNC

    Args:
        ibs (IBEISController):  ibeis controller object
        aid (int):  annotation id
        mode (str):

    CommandLine:
        alias show_annot_weights='python -m ibeis.model.hots.vsone_pipeline --test-show_annot_weights --show'
        show_annot_weights
        show_annot_weights --db PZ_MTEST --aid 1 --mode 'dstncvs'
        show_annot_weights --db PZ_MTEST --aid 1 --mode 'fgweight'&
        show_annot_weights --db GZ_ALL --aid 1 --mode 'dstncvs'
        show_annot_weights --db GZ_ALL --aid 1 --mode 'fgweight'&


        python -m ibeis.model.hots.vsone_pipeline --test-show_annot_weights --show --db GZ_ALL --aid 1 --mode 'dstncvs'
        python -m ibeis.model.hots.vsone_pipeline --test-show_annot_weights --show --db PZ_MTEST --aid 1 --mode 'dstncvs'
        python -m ibeis.model.hots.vsone_pipeline --test-show_annot_weights --show --db GZ_ALL --aid 1 --mode 'fgweight'
        python -m ibeis.model.hots.vsone_pipeline --test-show_annot_weights --show --db PZ_MTEST --aid 1 --mode 'fgweight'

        python -m ibeis.model.hots.vsone_pipeline --test-show_annot_weights --show --db GZ_ALL --aid 1 --mode 'dstncvs*fgweight'
        python -m ibeis.model.hots.vsone_pipeline --test-show_annot_weights --show --db PZ_MTEST --aid 1 --mode 'dstncvs*fgweight'

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.model.hots.vsone_pipeline import *  # NOQA
        >>> import plottool as pt
        >>> import ibeis
        >>> # build test data
        >>> ibs = ibeis.opendb(ut.get_argval('--db', type_=str, default='testdb1'))
        >>> aid = ut.get_argval('--aid', type_=int, default=1)
        >>> mode = ut.get_argval('--mode', type_=str, default='dstncvs')
        >>> # execute function
        >>> show_annot_weights(ibs, aid, mode)
        >>> pt.show_if_requested()
    """
    import functools
    import plottool as pt
    fnum = 1
    chipsize = ibs.get_annot_chipsizes(aid)
    #chipshape = chipsize[::-1]
    chip = ibs.get_annot_chips(aid)
    kpts = ibs.get_annot_kpts(aid)
    mode = mode.strip('\'')  # win32 hack
    fx2_score = 1.0
    weight_fn_dict = {
        'dstncvs': functools.partial(get_kpts_distinctiveness, ibs),
        'fgweight': ibs.get_annot_fgweights,
    }
    key_list = mode.split('*')
    for key in key_list:
        #print(key)
        get_weight = weight_fn_dict[key]
        fx2_weight = get_weight([aid])[0]
        #print(fx2_weight)
        fx2_score = fx2_score * fx2_weight
    fx2_score **= 1.0 / len(key_list)  # geometric average
    #mask, patch = coverage_image.make_coverage_mask(
    #    kpts, chipshape, fx2_score=fx2_score, mode='max')
    mask = coverage_image.get_grid_coverage_mask(
        kpts, chipsize, fx2_score, grid_scale_factor=.5, grid_steps=2, grid_sigma=3.0,
        resize=True)
    #mask = (mask / mask.max()) ** 2
    coverage_image.show_coverage_map(chip, mask, None, kpts, fnum, ell_alpha=.2, show_mask_kpts=False)
    pt.set_figtitle(mode)


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.model.hots.vsone_pipeline
        python -m ibeis.model.hots.vsone_pipeline --allexamples
        python -m ibeis.model.hots.vsone_pipeline --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()

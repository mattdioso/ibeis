from __future__ import absolute_import, division, print_function
import utool
import numpy as np
from scipy.cluster.hierarchy import fclusterdata
from sklearn.cluster import MeanShift, estimate_bandwidth
#from ibeis import constants
(print, print_, printDBG, rrr, profile) = utool.inject(
    __name__, '[preproc_encounter]', DEBUG=False)


def ibeis_compute_encounters(ibs, gid_list):
    """
    clusters encounters togethers (by time, not yet space)
    An encounter is a meeting, localized in time and space between a camera and
    a group of animals.  Animals are identified within each encounter.
    """
    print('[encounter] computing encounters on %r images' % len(gid_list))
    if len(gid_list) == 0:
        print('[encounter] WARNING: No unixtime data to compute encounters with')
        return [], []
    # Config info
    enc_cfg_uid      = ibs.cfg.enc_cfg.get_uid()
    seconds_thresh   = ibs.cfg.enc_cfg.seconds_thresh
    min_imgs_per_enc = ibs.cfg.enc_cfg.min_imgs_per_encounter
    cluster_algo     = ibs.cfg.enc_cfg.cluster_algo
    quantile         = ibs.cfg.enc_cfg.quantile
    # Data to cluster
    unixtime_list = ibs.get_image_unixtime(gid_list)
    gid_arr       = np.array(gid_list)
    unixtime_arr  = np.array(unixtime_list)
    # Agglomerative clustering of unixtimes
    if cluster_algo == 'agglomerative':
        label_arr = _agglomerative_cluster_encounters_time(unixtime_arr, seconds_thresh)
    elif cluster_algo == 'meanshift':
        label_arr = _meanshift_cluster_encounters_time(unixtime_arr, quantile)
    else:
        raise AssertionError('Uknown clustering algorithm: %r' % cluster_algo)
    # Group images by unique label
    labels, label_gids = _group_images_by_label(label_arr, gid_arr)
    # Remove encounters less than the threshold
    enc_labels, enc_gids = _filter_and_relabel(labels, label_gids, min_imgs_per_enc)
    # Flatten gids list by enounter
    flat_eids, flat_gids = utool.flatten_membership_mapping(enc_labels, enc_gids)
    # Create enctext for each image
    #enctext_list = [constants.ENCTEXT_PREFIX + repr(eid) for eid in flat_eids]
    enctext_list = [enc_cfg_uid + repr(eid) for eid in flat_eids]
    print('[encounter] found %d clusters' % len(labels))
    return enctext_list, flat_gids


def _agglomerative_cluster_encounters_time(unixtime_arr, seconds_thresh):
    """ Agglomerative encounter clustering algorithm
    Input: Length N array of data to cluster
    Output: Length N array of labels
    """
    # scipy clustering requires 2d input
    X_data = np.vstack([unixtime_arr, np.zeros(unixtime_arr.size)]).T
    label_arr = fclusterdata(X_data, seconds_thresh, criterion='distance')
    return label_arr


def _meanshift_cluster_encounters_time(unixtime_arr, quantile):
    """ Meanshift encounter clustering algorithm
    Input: Length N array of data to cluster
    Output: Length N array of labels
    """
    # scipy clustering requires 2d input
    X_data = np.vstack([unixtime_arr, np.zeros(unixtime_arr.size)]).T
    # quantile should be between [0, 1]
    # e.g: quantile=.5 represents the median of all pairwise distances
    try:
        bandwidth = estimate_bandwidth(X_data, quantile=quantile, n_samples=500)
        if bandwidth == 0:
            print('[WARNING!] bandwidth is 0. Cannot cluster')
            return np.zeros(unixtime_arr.size)
        # bandwidth is with respect to the RBF used in clustering
        ms = MeanShift(bandwidth=bandwidth, bin_seeding=True, cluster_all=True)
        ms.fit(X_data)
        label_arr = ms.labels_
    except Exception as ex:
        utool.printex(ex, 'error computing meanshift', key_list=['X_data',
                                                                 'quantile'])
        raise
    return label_arr


def _group_images_by_label(labels_arr, gid_arr):
    """
    Input: Length N list of labels and ids
    Output: Length M list of unique labels, and lenth M list of lists of ids
    """
    # Reverse the image to cluster index mapping
    label2_gids = utool.build_reverse_mapping(gid_arr, labels_arr)
    # Unpack dict, sort encounters by images-per-encounter
    labels, label_gids = utool.unpack_items_sorted_by_lenvalue(label2_gids)
    labels     = np.array(labels)
    label_gids = np.array(label_gids)
    return labels, label_gids


def _filter_and_relabel(labels, label_gids, min_imgs_per_enc):
    """
    Removes clusters with too few members.
    Relabels clusters-labels such that label 0 has the most members
    """
    label_nGids = np.array(map(len, label_gids))
    label_isvalid = label_nGids >= min_imgs_per_enc
    # Rebase ids so encounter0 has the most images
    enc_ids  = range(label_isvalid.sum())
    enc_gids = label_gids[label_isvalid]
    return enc_ids, enc_gids

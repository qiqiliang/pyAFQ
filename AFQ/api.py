import pandas as pd
import glob
import os.path as op

import numpy as np

import nibabel as nib
import dipy.core.gradients as dpg
from dipy.segment.mask import median_otsu


def do_preprocessing():
    raise NotImplementedError

#
# # Set the default set as a module-wide constant:
# BUNDLE_NAMES = ["ATR", "CGC", "CST",
#                # "FA", "FP",
#                "HCC", "IFO", "ILF",
#                "SLF", "ARC", "UNC"]
#
# # Read in the standard templates:
# AFQ_TEMPLATES = afd.read_templates()
# # For the arcuate, we need to rename a few of these and duplicate the SLF
# # ROI:
# AFQ_TEMPLATES['ARC_roi1_L'] = AFQ_TEMPLATES['SLF_roi1_L']
# AFQ_TEMPLATES['ARC_roi1_R'] = AFQ_TEMPLATES['SLF_roi1_R']
# AFQ_TEMPLATES['ARC_roi2_L'] = AFQ_TEMPLATES['SLFt_roi2_L']
# AFQ_TEMPLATES['ARC_roi2_R'] = AFQ_TEMPLATES['SLFt_roi2_R']
#
# #AFQ_BUNDLES = {'name': {'ROIs':[img, img], 'rules':[True, True]}}
# AFQ_BUNDLES = {}
#
# for name in BUNDLE_NAMES:
#     for hemi in ["R", "L"]:
#         AFQ_BUNDLES[name] = [[r for r in AFQ_TEMPLATES[]]]


class AFQ(object):
    """
    Requires the following file structure:

    study_folder/
                sub-01
                sub-02/sess-test
                sub-02/sess-retest/anat/T1w.nii.gz
                sub-02/sess-retest/dwi/dwi.nii.gz
                sub-02/sess-retest/dwi/dwi.bvals
                sub-02/sess-retest/dwi/dwi.bvecs


    All subjects'/sessions' dwi_prefix needs to be the same!

    That is, you *can't* have:

        sub-01/sess-test/dwi/dwi.nii.gz
        sub-02/sess-retest/dwi/dwi_foo.nii.gz

    Even though these are different subjects/sessions/etc.

    Instead you can (and must!) have:

        sub-01/sess-test/dwi/mydata_foo.nii.gz
        sub-02/sess-retest/dwi/mydata_foo.nii.gz

    Where any part of this string (e.g. "foo") can report on things like the
    number of directions, the preprocessing that happened, etc.

    """
    def __init__(self, raw_path=None, preproc_path=None,
                 sub_prefix="sub", dwi_folder="dwi",
                 dwi_file="*dwi*", anat_folder="anat",
                 anat_file="*T1w*"):
        self.raw_path = raw_path
        self.preproc_path = preproc_path
        if self.preproc_path is None:
            if self.raw_path is None:
                e_s = "must provide either preproc_path or raw_path (or both)"
                raise ValueError(e_s)
            # This creates the preproc_path such that:
            self.preproc_path = do_preprocessing(self.raw_path)
        # This is the place in which each subject's full data lives
        self.subject_dirs = glob.glob(op.join(preproc_path,
                                              '%s*' % sub_prefix))
        self.subjects = [op.split(p)[-1] for p in self.subject_dirs]
        sub_list = []
        sess_list = []
        dwi_file_list = []
        bvec_file_list = []
        bval_file_list = []
        anat_file_list = []
        for subject, sub_dir in zip(self.subjects, self.subject_dirs):
            sessions = glob.glob(op.join(sub_dir, '*'))
            for sess in sessions:
                dwi_file_list.append(glob.glob(op.join(sub_dir,
                                                       ('%s/%s/%s.nii.gz' %
                                                        (sess, dwi_folder,
                                                         dwi_file))))[0])

                bvec_file_list.append(glob.glob(op.join(sub_dir,
                                                        ('%s/%s/%s.bvec*' %
                                                         (sess, dwi_folder,
                                                          dwi_file))))[0])

                bval_file_list.append(glob.glob(op.join(sub_dir,
                                                        ('%s/%s/%s.bval*' %
                                                         (sess, dwi_folder,
                                                          dwi_file))))[0])

                anat_file_list.append(glob.glob(op.join(sub_dir,
                                                        ('%s/%s/%s.nii.gz' %
                                                         (sess,
                                                          anat_folder,
                                                          anat_file))))[0])
                sub_list.append(subject)
                sess_list.append(sess)

        self.data_frame = pd.DataFrame(dict(subject=sub_list,
                                            dwi_file=dwi_file_list,
                                            bvec_file=bvec_file_list,
                                            bval_file=bval_file_list,
                                            anat_file=anat_file_list,
                                            sess=sess_list))
        self.init_gtab()
        self.init_affine()

    def init_affine(self):
        affine_list = []
        for fdwi in self.data_frame['dwi_file']:
            affine_list.append(nib.load(fdwi).get_affine())
        self.data_frame['dwi_affine'] = affine_list

    def init_gtab(self):
        gtab_list = []
        for fbval, fbvec in zip(self.data_frame['bval_file'],
                                self.data_frame['bvec_file']):
            gtab_list.append(dpg.gradient_table(fbval, fbvec))
        self.data_frame['gtab'] = gtab_list

    def brain_extraction(self, median_radius=4, numpass=4, autocrop=False,
                         vol_idx=None, dilate=None, force_recompute=False):
            self.data_frame['brain_mask_file'] =\
                self.data_frame.apply(_brain_extract_fname, axis=1)

            self.data_frame['brain_mask_img'] =\
                self.data_frame.apply(_brain_extract, axis=1,
                                      median_radius=median_radius,
                                      numpass=numpass,
                                      autocrop=autocrop,
                                      vol_idx=vol_idx,
                                      dilate=dilate,
                                      force_recompute=force_recompute)

    def fit_tensors():
        raise NotImplementedError


def _brain_extract_fname(row):
    split_fdwi = op.split(row['dwi_file'])
    be_fname = op.join(split_fdwi[0], split_fdwi[1].split('.')[0] +
                       '_brain_mask.nii.gz')
    return be_fname


def _brain_extract(row, median_radius=4, numpass=4, autocrop=False,
                   vol_idx=None, dilate=None, force_recompute=False):
    if not op.exists(row['brain_mask_file']) or force_recompute:
        img = nib.load(row['dwi_file'])
        data = img.get_data()
        gtab = row['gtab']
        mean_b0 = np.mean(data[..., ~gtab.b0s_mask], -1)
        _, brain_mask = median_otsu(mean_b0, median_radius, numpass,
                                    autocrop, dilate=dilate)
        be_img = nib.Nifti1Image(brain_mask.astype(int),
                                 img.affine)
        nib.save(be_img, row['brain_mask_file'])
        return be_img
    else:
        return nib.load(row['brain_mask_file'])

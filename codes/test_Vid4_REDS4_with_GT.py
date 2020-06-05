'''
Test Vid4 (SR) and REDS4 (SR-clean, SR-blur, deblur-clean, deblur-compression) datasets
'''

import os
import os.path as osp
import glob
import logging
import numpy as np
import cv2
import torch

import utils.util as util
import data.util as data_util
import models.archs.EDVR_arch as EDVR_arch


def main():
    #################
    # configurations
    #################
    device = torch.device('cuda')
    os.environ['CUDA_VISIBLE_DEVICES'] = '0'
    data_mode = 'Vid4'  # Vid4 | sharp_bicubic | blur_bicubic | blur | blur_comp
    # Vid4: SR
    # REDS4: sharp_bicubic (SR-clean), blur_bicubic (SR-blur);
    #        blur (deblur-clean), blur_comp (deblur-compression).
    stage = 1  # 1 or 2, use two stage strategy for REDS dataset.
    flip_test = False
    ############################################################################
    #### model
    if data_mode == 'Vid4':
        if stage == 1:
            model_path = '../experiments/pretrained_models/cinepak_small2.pth'
        else:
            raise ValueError('Vid4 does not support stage 2.')
    elif data_mode == 'sharp_bicubic':
        if stage == 1:
            model_path = '../experiments/pretrained_models/EDVR_REDS_SR_L.pth'
        else:
            model_path = '../experiments/pretrained_models/EDVR_REDS_SR_Stage2.pth'
    elif data_mode == 'blur_bicubic':
        if stage == 1:
            model_path = '../experiments/pretrained_models/EDVR_REDS_SRblur_L.pth'
        else:
            model_path = '../experiments/pretrained_models/EDVR_REDS_SRblur_Stage2.pth'
    elif data_mode == 'blur':
        if stage == 1:
            model_path = '../experiments/pretrained_models/EDVR_REDS_deblur_L.pth'
        else:
            model_path = '../experiments/pretrained_models/EDVR_REDS_deblur_Stage2.pth'
    elif data_mode == 'blur_comp':
        if stage == 1:
            model_path = '../experiments/pretrained_models/EDVR_REDS_deblurcomp_L.pth'
        else:
            model_path = '../experiments/pretrained_models/EDVR_REDS_deblurcomp_Stage2.pth'
    else:
        raise NotImplementedError

    if data_mode == 'Vid4':
        N_in = 7  # use N_in images to restore one HR image
    else:
        N_in = 5

    predeblur, HR_in = False, False
    back_RBs = 10
    if data_mode == 'blur_bicubic':
        predeblur = True
    if data_mode == 'blur' or data_mode == 'blur_comp':
        predeblur, HR_in = True, True
    if stage == 2:
        HR_in = True
        back_RBs = 20
    model = EDVR_arch.EDVR(64, N_in, 8, 5, back_RBs, predeblur=predeblur, HR_in=HR_in)

    #### dataset
    if data_mode == 'Vid4':
        test_dataset_folder = '../datasets/Vid4/BIx4'
        GT_dataset_folder = '../datasets/Vid4/GT'
    else:
        if stage == 1:
            test_dataset_folder = '../datasets/REDS4/{}'.format(data_mode)
        else:
            test_dataset_folder = '../results/REDS-EDVR_REDS_SR_L_flipx4'
            print('You should modify the test_dataset_folder path for stage 2')
        GT_dataset_folder = '../datasets/REDS4/GT'

    #### evaluation
    crop_border = 0
    border_frame = N_in // 2  # border frames when evaluate
    # temporal padding mode
    if data_mode == 'Vid4' or data_mode == 'sharp_bicubic':
        padding = 'new_info'
    else:
        padding = 'replicate'
    save_imgs = True

    save_folder = '../results/{}'.format(data_mode)
    util.mkdirs(save_folder)
    util.setup_logger('base', save_folder, 'test', level=logging.INFO, screen=True, tofile=True)
    logger = logging.getLogger('base')

    #### log info
    logger.info('Data: {} - {}'.format(data_mode, test_dataset_folder))
    logger.info('Padding mode: {}'.format(padding))
    logger.info('Model path: {}'.format(model_path))
    logger.info('Save images: {}'.format(save_imgs))
    logger.info('Flip test: {}'.format(flip_test))

    #### set up the models
    model.load_state_dict(torch.load(model_path), strict=True)
    model.eval()
    model = model.to(device)

    avg_psnr_l, avg_psnr_center_l, avg_psnr_border_l = [], [], []
    subfolder_name_l = []

    subfolder_l = sorted(glob.glob(osp.join(test_dataset_folder, '*')))
    # for each subfolder
    for subfolder in subfolder_l:
        print('Processing video {:s}'.format(subfolder))
        subfolder_name = osp.basename(subfolder)
        subfolder_name_l.append(subfolder_name)
        save_subfolder = osp.join(save_folder, subfolder_name)

        img_path_l = sorted(glob.glob(osp.join(subfolder, '*')))
        max_idx = len(img_path_l)
        if save_imgs:
            util.mkdirs(save_subfolder)

        #### read LQ and GT images
        imgs_LQ = data_util.read_img_seq(subfolder)

        # process each image
        for img_idx, img_path in enumerate(img_path_l):
            print('\tProcessing frame {:s}')
            img_name = osp.splitext(osp.basename(img_path))[0]
            select_idx = data_util.index_generation(img_idx, max_idx, N_in, padding=padding)
            imgs_in = imgs_LQ.index_select(0, torch.LongTensor(select_idx)).unsqueeze(0).to(device)

            output = util.single_forward(model, imgs_in)
            output = util.tensor2img(output.squeeze(0))

            cv2.imwrite(osp.join(save_subfolder, '{}.png'.format(img_name)), output)

if __name__ == '__main__':
    main()

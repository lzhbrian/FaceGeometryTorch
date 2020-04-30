import cv2
import sys
import matplotlib.pyplot as plt
import numpy as np
from psbody.mesh import Mesh
from utils.render_mesh import render_mesh
from Yam_research.utils.utils import CoordTransformer


def on_step(mesh, renderer, target_img, target_lmks, opt_lmks, lmk_dist=0.0, shape_reg=0.0, exp_reg=0.0,
            neck_pose_reg=0.0, jaw_pose_reg=0.0, eyeballs_pose_reg=0.0):
    if lmk_dist > 0.0 or shape_reg > 0.0 or exp_reg > 0.0 or neck_pose_reg > 0.0 or jaw_pose_reg > 0.0 or eyeballs_pose_reg > 0.0:
        print('lmk_dist: %f, shape_reg: %f, exp_reg: %f, neck_pose_reg: %f, jaw_pose_reg: %f, eyeballs_pose_reg: %f' % (
            lmk_dist, shape_reg, exp_reg, neck_pose_reg, jaw_pose_reg, eyeballs_pose_reg))

    # transform coord system from [-1,1] to [n,m] of target img
    coord_transfromer = CoordTransformer(target_img.shape)
    # target lmks
    plt_target_lmks = target_lmks.copy()
    plt_target_lmks = coord_transfromer.cam2screen(plt_target_lmks)

    # model lmks
    plt_opt_lmks = opt_lmks.copy()
    plt_opt_lmks = coord_transfromer.cam2screen(plt_opt_lmks)

    for (x, y) in plt_target_lmks:
        cv2.circle(target_img, (int(x), int(y)), 4, (0, 0, 255), -1)

    for (x, y) in plt_opt_lmks:
        cv2.circle(target_img, (int(x), int(y)), 4, (255, 0, 0), -1)

    if sys.version_info >= (3, 0):
        # rendered_img = render_mesh(Mesh(scale * verts, faces), height=target_img.shape[0], width=target_img.shape[1])
        rendered_img = renderer.render_phong(mesh)
        rendered_img = rendered_img.detach().cpu().numpy().squeeze()
        rendered_img = cv2.resize(rendered_img, (target_img.shape[0], target_img.shape[1]))
        # rendered_img = cv2.UMat(np.array(rendered_img, dtype=np.uint8))
        for (x, y) in plt_opt_lmks:
            cv2.circle(rendered_img, (int(x), int(y)), 4, (0, 255, 0), -1)

        # target_img = np.hstack((target_img, rendered_img[:,:,:3]))

    cv2.imshow('target_img', target_img)
    cv2.waitKey()
    cv2.imshow('rendered img', rendered_img)
    cv2.waitKey()

    # cv2.imshow('img', target_img)
    # cv2.waitKey(10)
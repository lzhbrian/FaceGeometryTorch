import numpy as np
import torch
from flame import FlameDecoder
import pyrender
import trimesh
from config import get_config

from vtkplotter import Plotter, datadir, Text2D, show, interactive
import vtkplotter.mesh
import time
from flame import FlameLandmarks
import os
import torch
import numpy as np
from tqdm import tqdm_notebook
import imageio
import torch.nn as nn
import torch.nn.functional as F
import matplotlib.pyplot as plt
from skimage import img_as_ubyte
from config import *

# io utils
from pytorch3d.io import load_obj

# datastructures
from pytorch3d.structures import Meshes, Textures

# 3D transformations functions
from pytorch3d.transforms import Rotate, Translate

# rendering components
from pytorch3d.renderer import (
    OpenGLPerspectiveCameras, look_at_view_transform, look_at_rotation,
    RasterizationSettings, MeshRenderer, MeshRasterizer, BlendParams,
    SoftSilhouetteShader, HardPhongShader, PointLights
)
from fitting.silhouette_fitting import segment_img
from Yam_research.utils.utils import make_mesh
import cv2
from torch.autograd import Variable

# Set the cuda device
device = torch.device("cuda:0")
torch.cuda.set_device(device)

config = get_config_with_default_args()
config.batch_size = 1
config.flame_model_path = 'model/male_model.pkl'

# Load the obj and ignore the textures and materials.
# verts, faces_idx, _ = load_obj("./data/teapot.obj")
verts, faces_idx, _ = load_obj(
    "/home/yam/arabastra/Israel/Tel_aviv/Yehoodit_5/common_ground/resultes/sentence01.000002.26_C.obj")
faces = faces_idx.verts_idx
print(type(faces))
print(faces)

# Initialize each vertex to be white in color.
verts_rgb = torch.ones_like(verts)[None]  # (1, V, 3)
textures = Textures(verts_rgb=verts_rgb.to(device))

print(type(verts))
print(type(faces))
print(type(textures))

# Create a Meshes object for the teapot. Here we have only one mesh in the batch.
face_mesh_alt = Meshes(
    verts=[verts.to(device)],
    faces=[faces.to(device)],
    textures=textures
)

# config = get_config()
# config.batch_size = 1
# config.flame_model_path = './model/male_model.pkl'
# config.use_3D_translation = True # could be removed, depending on the camera model
# config.use_face_contour = False

image_ref_loaded = cv2.imread('./data/bareteeth.000001.26_C.jpg')
image_ref_loaded = cv2.resize(image_ref_loaded, (256, 256))
image_ref_loaded = segment_img(image_ref_loaded, 10)

flamelayer = FlameLandmarks(config)
flamelayer.cuda()
verts, _, _ = flamelayer()
# Initialize each vertex to be white in color.
verts_rgb = torch.ones_like(verts)[None]  # (1, V, 3)
textures = Textures(verts_rgb=verts_rgb.to(device))
faces = torch.tensor(np.int32(flamelayer.faces), dtype=torch.long).cuda()
print(type(verts))
print(type(faces))
print(type(textures))
face_mesh = Meshes(
    verts=[verts.to(device)],
    faces=[faces.to(device)],
    textures=textures
)

##########################################################################

# Initialize an OpenGL perspective camera.
cameras = OpenGLPerspectiveCameras(device=device)

# To blend the 100 faces we set a few parameters which control the opacity and the sharpness of
# edges. Refer to blending.py for more details.
blend_params = BlendParams(sigma=1e-6, gamma=1e-6)

# Define the settings for rasterization and shading. Here we set the output image to be of size
# 256x256. To form the blended image we use 100 faces for each pixel. We also set bin_size and max_faces_per_bin to None which ensure that
# the faster coarse-to-fine rasterization method is used. Refer to rasterize_meshes.py for
# explanations of these parameters. Refer to docs/notes/renderer.md for an explanation of
# the difference between naive and coarse-to-fine rasterization.
raster_settings = RasterizationSettings(
    image_size=256,
    blur_radius=np.log(1. / 1e-4 - 1.) * blend_params.sigma,
    faces_per_pixel=100,
)

# Create a silhouette mesh renderer by composing a rasterizer and a shader.
silhouette_renderer = MeshRenderer(
    rasterizer=MeshRasterizer(
        cameras=cameras,
        raster_settings=raster_settings
    ),
    shader=SoftSilhouetteShader(blend_params=blend_params)
)

# We will also create a phong renderer. This is simpler and only needs to render one face per pixel.
raster_settings = RasterizationSettings(
    image_size=256,
    blur_radius=0.0,
    faces_per_pixel=1,
)
# We can add a point light in front of the object.
lights = PointLights(device=device, location=((2.0, 2.0, -2.0),))
phong_renderer = MeshRenderer(
    rasterizer=MeshRasterizer(
        cameras=cameras,
        raster_settings=raster_settings
    ),
    shader=HardPhongShader(device=device, lights=lights)
)

############################################################################3
# Select the viewpoint using spherical angles
distance = 0.3  # distance from camera to the object
elevation = 0.5  # angle of elevation in degrees
azimuth = 180.0  # No rotation so the camera is positioned on the +Z axis.

# Get the position of the camera based on the spherical angles
R, T = look_at_view_transform(distance, elevation, azimuth, device=device)

# Select the viewpoint using spherical angles
distance = 0.3  # distance from camera to the object
elevation = 5  # angle of elevation in degrees
azimuth = 0.0  # No rotation so the camera is positioned on the +Z axis.

# Get the position of the camera based on the spherical angles
R, T = look_at_view_transform(distance, elevation, azimuth, device=device)

# Render the teapot providing the values of R and T.
silhouete = silhouette_renderer(meshes_world=face_mesh, R=R, T=T)

# image_ref = phong_renderer(meshes_world=teapot_mesh, R=R, T=T)
# silhouete = silhouette_renderer(meshes_world=face_mesh, R=R, T=T)
image_ref = phong_renderer(meshes_world=face_mesh, R=R, T=T)

# image_ref = image_ref.cpu().detach().numpy()
image_ref = image_ref_loaded

print('im ref sum', np.sum(image_ref))
silhouete = silhouete.cpu().detach().numpy()


#############################################################################
# # LBFGS OPTIMIZATION
# image_ref_torch = torch.from_numpy((image_ref != 0).astype(np.float32)).to(device)
# camera_position = nn.Parameter(
#             torch.from_numpy(np.array([.0, 0.9, +.5], dtype=np.float32)).to(face_mesh_alt.device))
# vars = [camera_position]  # Optimize for global scale, translation and rotation
# rigid_scale_optimizer = torch.optim.LBFGS(vars, tolerance_change=1e-7, max_iter=1500, line_search_fn='strong_wolfe')
#
# factor = 1
#
#
# def image_fit_loss(face_mesh_alt):
#     R = look_at_rotation(camera_position[None, :], device=device)  # (1, 3, 3)
#     T = -torch.bmm(R.transpose(1, 2), camera_position[None, :, None])[:, :, 0]  # (1, 3)
#     silhouette = silhouette_renderer(meshes_world=face_mesh_alt.clone(), R=R, T=T).squeeze()[..., 3]
#     return torch.sum(torch.sub(silhouette, image_ref_torch) ** 2) / (factor ** 2)
#
#
# def fit_closure():
#     if torch.is_grad_enabled():
#         rigid_scale_optimizer.zero_grad()
#     # _, _, flame_regularizer_loss = flamelayer()
#     my_mesh = make_mesh(flamelayer, device)
#     obj1 = image_fit_loss(my_mesh)
#     obj = obj1 #+ flame_regularizer_loss
#     print(obj)
#     if obj.requires_grad:
#         obj.backward()
#     return obj
#
#
# #print image
# R = look_at_rotation(camera_position[None, :], device=device)
# T = -torch.bmm(R.transpose(1, 2), camera_position[None, :, None])[:, :, 0]  # (1, 3)
# image = silhouette_renderer(meshes_world=face_mesh_alt.clone(), R=R, T=T)
# image = image[..., 3].detach().squeeze().cpu().numpy()
# plt.subplot(121)
# plt.imshow(image)
# plt.subplot(122)
# plt.imshow(image_ref)
# plt.show()
#
# # plot_silhouette(flamelayer, renderer, image_ref, device)
# print('preoptimization sihouette')
# rigid_scale_optimizer.step(fit_closure)
# # plot_silhouette(flamelayer, renderer, image_ref, device)
# print('first optimization attempt')
#
# #print image
# R = look_at_rotation(camera_position[None, :], device=device)
# T = -torch.bmm(R.transpose(1, 2), camera_position[None, :, None])[:, :, 0]  # (1, 3)
# image = silhouette_renderer(meshes_world=face_mesh_alt.clone(), R=R, T=T)
# image = image[0, ..., 3].detach().squeeze().cpu().numpy()
# plt.subplot(121)
# plt.imshow(image)
# plt.subplot(122)
# plt.imshow(image_ref)
# plt.show()
#############################################################################
# Model for camera position
class Model(nn.Module):
    def __init__(self, meshes, renderer, image_ref):
        super().__init__()
        self.meshes = meshes
        self.device = meshes.device
        self.renderer = renderer

        # Get the silhouette of the reference RGB image by finding all the non zero values.
        # image_ref = torch.from_numpy((image_ref[..., :3].max(-1) != 0).astype(np.float32))
        image_ref = torch.from_numpy((image_ref != 0).astype(np.float32))
        self.register_buffer('image_ref', image_ref)

        # Create an optimizable parameter for the x, y, z position of the camera.
        self.camera_position = nn.Parameter(
            torch.from_numpy(np.array([3.0, 6.9, +2.5], dtype=np.float32)).to(meshes.device))

    def forward(self):
        # Render the image using the updated camera position. Based on the new position of the
        # camer we calculate the rotation and translation matrices
        R = look_at_rotation(self.camera_position[None, :], device=self.device)  # (1, 3, 3)
        T = -torch.bmm(R.transpose(1, 2), self.camera_position[None, :, None])[:, :, 0]  # (1, 3)
        image = self.renderer(meshes_world=self.meshes.clone(), R=R, T=T)

        # Calculate the silhouette loss
        loss = torch.sum((image[..., 3] - self.image_ref) ** 2)
        return loss, image


####################################################################################################


print('loop optimization ')
# We will save images periodically and compose them into a GIF.
filename_output = "Results/teapot_optimization_demo.gif"
writer = imageio.get_writer(filename_output, mode='I', duration=0.3)

# Initialize a model using the renderer, mesh and reference image
model = Model(meshes=face_mesh_alt, renderer=silhouette_renderer, image_ref=image_ref).to(device)
# model = Model(meshes=face_mesh, renderer=silhouette_renderer, image_ref=image_ref).to(device)

# Create an optimizer. Here we are using Adam and we pass in the parameters of the model
# optimizer = torch.optim.Adam(model.parameters(), lr=0.05)

camera_translation = Variable(torch.from_numpy(np.array([3.0, 6.9, +2.5], dtype=np.float32)).cuda(), requires_grad=True)
vars = [camera_translation]
optimizer = torch.optim.LBFGS(vars, max_iter=1500, tolerance_change=1e-7, line_search_fn='strong_wolfe')
image_ref_torch = torch.from_numpy((image_ref != 0).astype(np.float32)).to(device)
factor = 1


def image_fit_loss(face_mesh_alt):
    R = look_at_rotation(camera_translation[None, :], device=device)  # (1, 3, 3)
    T = -torch.bmm(R.transpose(1, 2), camera_translation[None, :, None])[:, :, 0]  # (1, 3)
    silhouette = silhouette_renderer(meshes_world=face_mesh_alt.clone(), R=R, T=T)
    print(type(silhouete))
    return torch.sum((silhouette[..., 3] - image_ref_torch) ** 2) / (factor ** 2)


def fit_closure():
    if torch.is_grad_enabled():
        optimizer.zero_grad()
    # _, _, flame_regularizer_loss = flamelayer()
    # my_mesh = make_mesh(flamelayer, device)

    loss = image_fit_loss(face_mesh_alt)
    # obj = obj1 + flame_regularizer_loss

    loss_model,_ = model()
    print('loss - ', loss)
    print('loss model - ', loss_model)
    obj = loss
    if obj.requires_grad:
        obj.backward()
    return obj

optimizer.step(fit_closure)
loss = image_fit_loss(face_mesh_alt)
R = look_at_rotation(camera_translation[None, :], device=model.device)
T = -torch.bmm(R.transpose(1, 2), camera_translation[None, :, None])[:, :, 0]  # (1, 3)
image = silhouette_renderer(meshes_world=face_mesh_alt.clone(), R=R, T=T)
image = image[..., 3].detach().squeeze().cpu().numpy()
image = img_as_ubyte(image)
writer.append_data(image)
print('long LBFGS')
plt.subplot(121)
plt.imshow(image)
plt.title("iter: %d, loss: %0.2f" % (1, loss.data))
plt.grid("off")
plt.axis("off")
plt.subplot(122)
plt.imshow(image_ref)
plt.grid("off")
plt.axis("off")
plt.show()

loop = tqdm_notebook(range(200))
for i in loop:
    optimizer.zero_grad()
    # loss, _ = model()
    # loss.backward()
    # optimizer.step()
    optimizer.step(fit_closure)
    loss = image_fit_loss(face_mesh_alt)
    loop.set_description('Optimizing (loss %.4f)' % loss.data)

    if loss.item() < 200:
        break
    # Save outputs to create a GIF.
    if i % 10 == 0:
        R = look_at_rotation(camera_translation[None, :], device=model.device)
        T = -torch.bmm(R.transpose(1, 2), camera_translation[None, :, None])[:, :, 0]  # (1, 3)
        image = silhouette_renderer(meshes_world=face_mesh_alt.clone(), R=R, T=T)
        image = image[..., 3].detach().squeeze().cpu().numpy()
        image = img_as_ubyte(image)
        writer.append_data(image)

        plt.subplot(121)
        plt.imshow(image)
        plt.title("iter: %d, loss: %0.2f" % (i, loss.data))
        plt.grid("off")
        plt.axis("off")
        plt.subplot(122)

        # silh_ref = torch.from_numpy((image_ref[..., :3].max(-1) != 0).astype(np.float32)).squeeze()
        # plt.imshow(silh_ref)
        plt.imshow(image_ref)

        plt.grid("off")
        plt.axis("off")

        plt.show()

plt.subplot(121)
plt.imshow(image[..., :3])
plt.title("iter: %d, loss: %0.2f" % (i, loss.data))
plt.grid("off")
plt.axis("off")
plt.subplot(122)
plt.show()
writer.close()

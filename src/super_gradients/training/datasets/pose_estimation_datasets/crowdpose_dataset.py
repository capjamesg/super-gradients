import os
from typing import Tuple, List, Mapping, Any, Union

import cv2
import numpy as np
from pycocotools.coco import COCO

from super_gradients.common.abstractions.abstract_logger import get_logger
from super_gradients.common.decorators.factory_decorator import resolve_param
from super_gradients.common.factories.target_generator_factory import TargetGeneratorsFactory
from super_gradients.common.factories.transforms_factory import TransformsFactory
from super_gradients.common.object_names import Datasets, Processings
from super_gradients.common.registry.registry import register_dataset
from super_gradients.training.datasets.data_formats.bbox_formats.xywh import xywh_to_xyxy, xyxy_to_xywh
from super_gradients.training.datasets.pose_estimation_datasets.base_keypoints import BaseKeypointsDataset
from super_gradients.training.transforms.keypoint_transforms import KeypointTransform, PoseEstimationSample

logger = get_logger(__name__)


@register_dataset(Datasets.CROWDPOSE_KEY_POINTS_DATASET)
class CrowdPoseKeypointsDataset(BaseKeypointsDataset):
    """
    Dataset class for training pose estimation models on Crowd Pose dataset.
    Use should pass a target generator class that is model-specific and generates the targets for the model.
    """

    @resolve_param("transforms", TransformsFactory())
    @resolve_param("target_generator", TargetGeneratorsFactory())
    def __init__(
        self,
        data_dir: str,
        images_dir: str,
        json_file: str,
        target_generator,
        transforms: List[KeypointTransform],
        min_instance_area: float,
        edge_links: Union[List[Tuple[int, int]], np.ndarray],
        edge_colors: Union[List[Tuple[int, int, int]], np.ndarray, None],
        keypoint_colors: Union[List[Tuple[int, int, int]], np.ndarray, None],
        crowd_annotations_action: str = "ignore",
    ):
        """

        :param data_dir: Root directory of the COCO dataset
        :param images_dir: path suffix to the images directory inside the dataset_root
        :param json_file: path suffix to the json file inside the dataset_root
            Otherwise, they will be filtered out.
        :param target_generator: Target generator that will be used to generate the targets for the model.
            See DEKRTargetsGenerator for an example.
        :param transforms: Transforms to be applied to the image & keypoints
        :param min_instance_area: Minimum area of an instance to be included in the dataset
        :param edge_links: Edge links between joints
        :param edge_colors: Color of the edge links. If None, the color will be generated randomly.
        :param keypoint_colors: Color of the keypoints. If None, the color will be generated randomly.
        :param crowd_annotations_action: Action to take for annotations with iscrowd=1. Can be one of the following:
            - "include" - These annotations will be treated as normal (non-crowd) annotations.
            - "ignore" - These annotations will be ignored. They would not contribute to the loss.
            - "remove" - These annotations will be removed from the dataset entirely.
        """

        if crowd_annotations_action not in ["include", "ignore", "remove"]:
            raise ValueError(f"crowd_annotations_action must be one of ['include', 'ignore', 'remove'], got {crowd_annotations_action}")

        json_file = os.path.join(data_dir, json_file)
        if not os.path.exists(json_file) or not os.path.isfile(json_file):
            raise FileNotFoundError(f"Annotation file {json_file} does not exist")

        coco = COCO(json_file)

        if crowd_annotations_action == "remove":
            from .coco_utils import remove_crowd_annotations

            coco = remove_crowd_annotations(coco)

        if len(coco.dataset["categories"]) != 1:
            raise ValueError("Dataset must contain exactly one category")
        joints = coco.dataset["categories"][0]["keypoints"]
        num_joints = len(joints)

        super().__init__(
            transforms=transforms,
            target_generator=target_generator,
            min_instance_area=min_instance_area,
            num_joints=num_joints,
            edge_links=edge_links,
            edge_colors=edge_colors,
            keypoint_colors=keypoint_colors,
        )
        self.root = data_dir
        self.images_dir = os.path.join(data_dir, images_dir)
        self.coco = coco
        self.ids = list(self.coco.imgs.keys())
        self.joints = joints
        self.crowd_annotations_action = crowd_annotations_action

    def __len__(self):
        return len(self.ids)

    def load_sample(self, index: int) -> PoseEstimationSample:
        """

        :param index:
        :return: Tuple of (image, mask, joints, instance areas, instance bounding boxes, is_crowd)
        """
        img_id = self.ids[index]
        image_info = self.coco.loadImgs(img_id)[0]
        file_name = image_info["file_name"]
        file_path = os.path.join(self.images_dir, file_name)
        ann_ids = self.coco.getAnnIds(imgIds=img_id)
        anno = self.coco.loadAnns(ann_ids)

        gt_iscrowd = np.array([bool(ann["iscrowd"]) for ann in anno]).reshape((-1))

        if self.crowd_annotations_action == "include":
            # If crowd_annotations_action is "include", we treat crowd annotations as normal annotations
            # so we set is_crowd to False for all annotations
            gt_iscrowd = np.zeros_like(gt_iscrowd, dtype=bool)

        gt_bboxes = np.array([ann["bbox"] for ann in anno], dtype=np.float32).reshape((-1, 4))
        gt_areas = gt_bboxes[:, 2] * gt_bboxes[:, 3] * 0.53

        orig_image = cv2.imread(file_path, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)

        if orig_image.shape[0] != image_info["height"] or orig_image.shape[1] != image_info["width"]:
            raise RuntimeError(f"Annotated image size ({image_info['height'],image_info['width']}) does not match image size in file {orig_image.shape[:2]}")

        # clip bboxes (xywh) to image boundaries
        xyxy_bboxes = xywh_to_xyxy(gt_bboxes, image_shape=None)
        image_height, image_width = orig_image.shape[:2]
        xyxy_bboxes[:, 0] = np.clip(xyxy_bboxes[:, 0], 0, image_width)
        xyxy_bboxes[:, 1] = np.clip(xyxy_bboxes[:, 1], 0, image_height)
        xyxy_bboxes[:, 2] = np.clip(xyxy_bboxes[:, 2], 0, image_width)
        xyxy_bboxes[:, 3] = np.clip(xyxy_bboxes[:, 3], 0, image_height)
        gt_bboxes = xyxy_to_xywh(xyxy_bboxes, image_shape=None)

        joints: np.ndarray = self.get_joints(anno)
        mask: np.ndarray = np.ones((image_height, image_width), dtype=np.uint8)

        return PoseEstimationSample(
            image=orig_image,
            mask=mask,
            joints=joints,
            areas=gt_areas,
            bboxes=gt_bboxes,
            is_crowd=gt_iscrowd,
        )

    def get_joints(self, anno: List[Mapping[str, Any]]) -> np.ndarray:
        """
        Decode the keypoints from the COCO annotation and return them as an array of shape [Num Instances, Num Joints, 3].
        The visibility of keypoints is encoded in the third dimension of the array with following values:
         - 0 being invisible (outside image)
         - 1 present in image but occluded
         - 2 - fully visible
        :param anno:
        :return: [Num Instances, Num Joints, 3], where last channel represents (x, y, visibility)
        """
        joints = []

        for i, obj in enumerate(anno):
            keypoints = np.array(obj["keypoints"]).reshape([-1, 3])
            joints.append(keypoints)

        num_instances = len(joints)
        joints = np.array(joints, dtype=np.float32).reshape((num_instances, self.num_joints, 3))
        return joints

    def get_dataset_preprocessing_params(self):
        """

        :return:
        """
        # Since we are using cv2.imread to read images, our model in fact is trained on BGR images.
        # In our pipelines the convention that input images are RGB, so we need to reverse the channels to get BGR
        # to match with the expected input of the model.
        pipeline = [Processings.ReverseImageChannels] + self.transforms.get_equivalent_preprocessing()
        params = dict(
            conf=0.05,
            image_processor={Processings.ComposeProcessing: {"processings": pipeline}},
            edge_links=self.edge_links,
            edge_colors=self.edge_colors,
            keypoint_colors=self.keypoint_colors,
        )
        return params

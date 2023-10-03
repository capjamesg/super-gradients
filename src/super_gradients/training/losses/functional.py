import math
from typing import Tuple

import torch
from torch import Tensor


def bbox_overlap(box1: Tuple[Tensor, Tensor, Tensor, Tensor], box2: Tuple[Tensor, Tensor, Tensor, Tensor], eps: float = 1e-10) -> Tuple[Tensor, Tensor, Tensor]:
    """
    Calculate the iou of box1 and box2.

    :param box1:    box1 with the shape (..., 4)
    :param box2:    box1 with the shape (..., 4)
    :param eps:     epsilon to avoid divide by zero
    :return:
        - iou:      iou of box1 and box2
        - overlap:  overlap of box1 and box2
        - union:    union of box1 and box2
    """
    x1, y1, x2, y2 = box1
    x1g, y1g, x2g, y2g = box2

    xkis1 = torch.maximum(x1, x1g)
    ykis1 = torch.maximum(y1, y1g)
    xkis2 = torch.minimum(x2, x2g)
    ykis2 = torch.minimum(y2, y2g)
    w_inter = (xkis2 - xkis1).clip(0)
    h_inter = (ykis2 - ykis1).clip(0)
    overlap = w_inter * h_inter

    area1 = (x2 - x1) * (y2 - y1)
    area2 = (x2g - x1g) * (y2g - y1g)
    union = area1 + area2 - overlap + eps
    iou = overlap / union

    return iou, overlap, union


def get_convex_bbox(box1: Tuple[Tensor, Tensor, Tensor, Tensor], box2: Tuple[Tensor, Tensor, Tensor, Tensor]):
    b1_x1, b1_y1, b1_x2, b1_y2 = box1
    b2_x1, b2_y1, b2_x2, b2_y2 = box2

    xc1 = torch.minimum(b1_x1, b2_x1)
    yc1 = torch.minimum(b1_y1, b2_y1)
    xc2 = torch.maximum(b1_x2, b2_x2)
    yc2 = torch.maximum(b1_y2, b2_y2)

    return xc1, yc1, xc2, yc2


def get_bbox_center(bbox: Tuple[Tensor, Tensor, Tensor, Tensor]):
    b1_x1, b1_y1, b1_x2, b1_y2 = bbox
    cx = (b1_x1 + b1_x2) * 0.5
    cy = (b1_y1 + b1_y2) * 0.5
    return cx, cy


def get_bbox_width_height(bbox: Tuple[Tensor, Tensor, Tensor, Tensor]):
    b1_x1, b1_y1, b1_x2, b1_y2 = bbox
    w = b1_x2 - b1_x1
    h = b1_y2 - b1_y1
    return w, h


def bbox_ciou_loss(pred_bboxes: Tensor, target_bboxes: Tensor, eps: float) -> Tensor:
    """
    Compute CIoU loss between predicted and target bboxes.
    :param pred_bboxes:   Predicted boxes in xyxy format of [D0, D1,...Di, 4] shape
    :param target_bboxes: Target boxes in xyxy format of [D0, D1,...Di, 4] shape
    :return: CIoU loss per each box as tensor of shape [D0, D1,...Di]
    """

    b1_x1, b1_y1, b1_x2, b1_y2 = pred_bboxes.chunk(4, dim=-1)
    b2_x1, b2_y1, b2_x2, b2_y2 = target_bboxes.chunk(4, dim=-1)

    box1 = [b1_x1, b1_y1, b1_x2, b1_y2]
    box2 = [b2_x1, b2_y1, b2_x2, b2_y2]
    iou, overlap, union = bbox_overlap(box1, box2, eps)

    iou_term = 1 - iou

    xc1 = torch.minimum(b1_x1, b2_x1)
    yc1 = torch.minimum(b1_y1, b2_y1)
    xc2 = torch.maximum(b1_x2, b2_x2)
    yc2 = torch.maximum(b1_y2, b2_y2)

    cw = xc2 - xc1
    ch = yc2 - yc1

    # convex diagonal squared
    diagonal_distance_squared = cw**2 + ch**2

    # compute center distance squared
    b1_cx = (b1_x1 + b1_x2) / 2
    b1_cy = (b1_y1 + b1_y2) / 2
    b2_cx = (b2_x1 + b2_x2) / 2
    b2_cy = (b2_y1 + b2_y2) / 2

    centers_distance_squared = (b1_cx - b2_cx) ** 2 + (b1_cy - b2_cy) ** 2
    distance_term = centers_distance_squared / (diagonal_distance_squared + eps)

    c2 = cw**2 + ch**2 + eps  # noqa

    # centerpoint distance squared
    w1, h1 = b1_x2 - b1_x1, b1_y2 - b1_y1
    w2, h2 = b2_x2 - b2_x1, b2_y2 - b2_y1
    v = (4 / math.pi**2) * torch.pow(
        torch.atan(w2 / h2) - torch.atan(w1 / h1),
        2,
    )
    with torch.no_grad():
        alpha = v / ((1 - iou) + v).clamp_min(eps)

    aspect_ratio_term = v * alpha

    return iou_term + distance_term + aspect_ratio_term  # CIoU


def bbox_focal_eiou_loss(pred_bboxes: Tensor, target_bboxes: Tensor, gamma: float, eps: float) -> Tensor:
    """
    Compute Focal-EIoU loss between predicted and target bboxes.
    https://arxiv.org/abs/2101.08158

    :param pred_bboxes:   Predicted boxes in xyxy format of [D0, D1,...Di, 4] shape
    :param target_bboxes: Target boxes in xyxy format of [D0, D1,...Di, 4] shape
    :return: CIoU loss per each box as tensor of shape [D0, D1,...Di]
    """

    box1 = pred_bboxes.chunk(4, dim=-1)
    box2 = target_bboxes.chunk(4, dim=-1)

    iou, overlap, union = bbox_overlap(box1, box2, eps)

    iou_term = 1 - iou

    # convex diagonal squared
    convex_box = get_convex_bbox(box1, box2)
    convex_box_width, convex_box_height = get_bbox_center(convex_box)
    diagonal_distance_squared = convex_box_width**2 + convex_box_height**2

    # centers of boxes
    b1_cx, b1_cy = get_bbox_center(box1)
    b2_cx, b2_cy = get_bbox_center(box2)

    # width and height of boxes
    w1, h1 = get_bbox_width_height(box1)
    w2, h2 = get_bbox_width_height(box2)

    # compute center distance squared
    centers_distance_squared = (b1_cx - b2_cx) ** 2 + (b1_cy - b2_cy) ** 2
    distance_term = centers_distance_squared / (diagonal_distance_squared + eps)

    eiou_term = (h1 - h2) ** 2 / convex_box_height + (w1 - w2) ** 2 / convex_box_width
    eiou = iou_term + distance_term + eiou_term

    scale_factor = torch.pow(iou, gamma)
    return eiou * scale_factor

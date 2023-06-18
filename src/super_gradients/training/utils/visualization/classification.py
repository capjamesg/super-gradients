from typing import Tuple

import cv2
import numpy as np


def draw_label(image: np.ndarray, label: str, confidence: float, image_shape: Tuple) -> np.ndarray:
    """Draw a label and confidence on an image.

    :param image:           Image on which to draw the bounding box.
    :param label:           Label to display on an image.
    :param confidence:      Confidence of the predicted label to display on an image
    :param image_shape:     Image shape of the image
    """

    # Determine the size of the label text
    (label_width, label_height), _ = cv2.getTextSize(text=label, fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.5, thickness=1)

    # Calculate the position to draw the label
    image_width, image_height = image_shape
    start_point = ((image_width - label_width) // 2, (image_height - label_height) // 4)
    # end_point = (start_point[0] + label_width, start_point[1] + label_height)

    # Draw a filled rectangle as the background for the label
    label_color = (0, 0, 0)
    bg_position = (start_point[0], start_point[1] - label_height)
    bg_size = (label_width, label_height + 5)
    cv2.rectangle(image, bg_position, (bg_position[0] + bg_size[0], bg_position[1] + bg_size[1]), label_color, thickness=-1)

    # Draw the label text on the image
    cv2.putText(
        img=image,
        text=label,
        org=start_point,
        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=0.5,
        color=(255, 255, 255),
        thickness=1,
        lineType=cv2.LINE_AA,
    )

    return image

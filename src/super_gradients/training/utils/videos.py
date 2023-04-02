from typing import List, Optional, Tuple
import cv2
import os

import numpy as np

SUPPORTED_FORMATS = (".avi", ".mp4", ".mov", ".wmv", ".mkv")


__all__ = ["load_video", "save_video"]


def load_video(file_path: str, max_frames: Optional[int] = None) -> List[np.ndarray]:
    """Open a video file and extract each frame into numpy array.

    :param file_path:   Path to the video file.
    :param max_frames:  Optional, maximum number of frames to extract.
    :return:            Frames representing the video, each in (H, W, C).
    """
    cap = _open_video(file_path)
    frames = _extract_frames(cap, max_frames)
    cap.release()
    return frames


def _open_video(file_path: str) -> cv2.VideoCapture:
    """Open a video file.

    :param file_path:   Path to the video file
    :return:            Opened video capture object
    """
    ext = os.path.splitext(file_path)[-1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise RuntimeError(f"Not supported video format {ext}. Supported formats: {SUPPORTED_FORMATS}")

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise ValueError(f"Failed to open video file: {file_path}")
    return cap


def _extract_frames(cap: cv2.VideoCapture, max_frames: Optional[int] = None) -> List[np.ndarray]:
    """Extract frames from an opened video capture object.

    :param cap:         Opened video capture object.
    :param max_frames:  Optional maximum number of frames to extract.
    :return:            Frames representing the video, each in (H, W, C).
    """
    frames = []

    while max_frames != len(frames):
        frame_read_success, frame = cap.read()
        if not frame_read_success:
            break
        frames.append(frame)

    return frames


def save_video(output_path: str, frames: List[np.ndarray], fps: int) -> None:
    """Save a video locally.

    :param output_path: Where the video will be saved
    :param frames:      Frames representing the video, each in (H, W, C). Note that all the frames are expected to have the same shape.
    :param fps:         Frames per second
    """
    video_height, video_width = _validate_frames(frames)

    video_writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (video_width, video_height),
    )

    for frame in frames:
        if frame.ndim == 2:
            frame = frame[:, :, np.newaxis]
        video_writer.write(frame)

    video_writer.release()


def _validate_frames(frames: List[np.ndarray]) -> Tuple[float, float]:
    """Validate the frames to make sure that every frame has the same size and includes the channel dimension. (i.e. (H, W, C))

    :param frames:  Frames representing the video, each in (H, W, C). Note that all the frames are expected to have the same shape.
    :return:        (Height, Weight) of the video.
    """
    min_height = min(frame.shape[0] for frame in frames)
    max_height = max(frame.shape[0] for frame in frames)

    min_width = min(frame.shape[1] for frame in frames)
    max_width = max(frame.shape[1] for frame in frames)

    if (min_height, min_width) != (max_height, max_width):
        raise RuntimeError(
            f"Your video is made of frames that have (height, width) going from ({min_height}, {min_width}) to ({max_height}, {max_width}).\n"
            f"Please make sure that all the frames have the same shape."
        )

    if set(frame.ndim for frame in frames) != {3} or set(frame.shape[-1] for frame in frames) != {3}:
        raise RuntimeError("Your frames must include 3 channels.")

    return max_height, max_width
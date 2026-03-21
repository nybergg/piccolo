"""
CameraManager — manages a Basler camera via pypylon.

Encapsulates the camera thread, frame grabbing, and settings.
All camera globals from the old piccolo_ui.py live here.
"""

import logging
import os
import threading
import time

import numpy as np

logger = logging.getLogger(__name__)

# Optional imports — camera support is not required
_CAMERA_LIBS_AVAILABLE = True
_CAMERA_IMPORT_ERROR = None
try:
    from pypylon import pylon
except ImportError as e:
    _CAMERA_LIBS_AVAILABLE = False
    _CAMERA_IMPORT_ERROR = f"pypylon: {e}"

try:
    import cv2
except ImportError as e:
    _CAMERA_LIBS_AVAILABLE = False
    _CAMERA_IMPORT_ERROR = f"opencv: {e}"


class CameraManager:
    """Manages a Basler camera lifecycle and frame streaming."""

    def __init__(self, hw_trigger=False, verbose=True):
        if not _CAMERA_LIBS_AVAILABLE:
            raise ImportError(f"Camera libraries not available: {_CAMERA_IMPORT_ERROR}")

        self.verbose = verbose
        self._hw_trigger = hw_trigger
        self._running = False
        self._thread = None
        self._camera = None

        self._frame_lock = threading.Lock()
        self._camera_lock = threading.Lock()
        self._latest_frame_jpeg = None
        self._recording = False
        self._record_frames = []
        self._record_filename = "recording.mp4"
        self._record_fps = 15

        # Create placeholder frame
        placeholder = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(placeholder, "Waiting for Camera...", (30, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 1)
        ret, jpeg = cv2.imencode('.jpg', placeholder)
        if ret:
            self._latest_frame_jpeg = jpeg.tobytes()

    @property
    def available(self):
        return _CAMERA_LIBS_AVAILABLE

    def start(self):
        """Start the camera grab thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._thread.start()
        logger.info("Camera thread started.")

    def stop(self):
        """Stop the camera grab thread and release the camera."""
        if not self._running:
            return
        self._running = False
        if self._thread:
            self._thread.join(timeout=7)
            if self._thread.is_alive():
                logger.warning("Camera thread did not stop in time.")
        logger.info("Camera thread stopped.")

    def restart(self, hw_trigger=None):
        """Stop and restart the camera, optionally changing trigger mode."""
        if hw_trigger is not None:
            self._hw_trigger = hw_trigger
        self.stop()
        self.start()

    def get_latest_frame(self):
        """Return the most recent JPEG frame as bytes, or None."""
        with self._frame_lock:
            return self._latest_frame_jpeg

    def set_exposure(self, us):
        """Set camera exposure time in microseconds."""
        with self._camera_lock:
            if self._camera and self._camera.IsOpen():
                self._camera.ExposureTime.SetValue(float(us))

    def set_trigger_delay(self, us):
        """Set camera trigger delay in microseconds."""
        with self._camera_lock:
            if self._camera and self._camera.IsOpen():
                self._camera.TriggerDelay.SetValue(float(us))

    def save_snapshot(self, filename="snapshot.png"):
        """Save the latest frame as an image file (PNG or JPEG based on extension)."""
        frame = self.get_latest_frame()
        if frame is None:
            logger.warning("No frame available to save.")
            return None
        if filename.lower().endswith('.png'):
            img = cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR)
            cv2.imwrite(filename, img)
        else:
            with open(filename, 'wb') as f:
                f.write(frame)
        logger.info("Snapshot saved to %s", filename)
        return filename

    def start_recording(self, filename="recording.mp4", fps=15):
        """Start recording frames to an MP4 file."""
        if self._recording:
            logger.warning("Already recording.")
            return
        self._recording = True
        self._record_filename = filename
        self._record_fps = fps
        self._record_frames = []
        logger.info("Recording started: %s", filename)

    def stop_recording(self):
        """Stop recording and write the video file."""
        if not self._recording:
            logger.warning("Not currently recording.")
            return None
        self._recording = False
        frames = self._record_frames
        self._record_frames = []

        if not frames:
            logger.warning("No frames captured during recording.")
            return None

        # Decode first frame to get dimensions
        first = cv2.imdecode(np.frombuffer(frames[0], np.uint8), cv2.IMREAD_COLOR)
        h, w = first.shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(self._record_filename, fourcc, self._record_fps, (w, h))
        for raw in frames:
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                writer.write(img)
        writer.release()
        logger.info("Recording saved to %s (%d frames)", self._record_filename, len(frames))
        return self._record_filename

    @property
    def is_recording(self):
        return self._recording

    def _grab_loop(self):
        """Camera grab thread — opens camera, grabs frames, encodes JPEG."""
        cam = None
        try:
            cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
            cam.Open()

            # Disable auto-features
            cam.ExposureAuto.SetValue("Off")
            cam.GainAuto.SetValue("Off")

            # Sensor config
            cam.Width.SetValue(2048)
            cam.Height.SetValue(2048)
            cam.PixelFormat.SetValue("Mono12p")

            # Trigger config
            mode = "On" if self._hw_trigger else "Off"
            cam.TriggerSelector.SetValue("FrameStart")
            cam.TriggerMode.SetValue(mode)
            cam.TriggerSource.SetValue("Line1")
            logger.debug("TriggerMode: %s", mode)

            # Initial parameters
            cam.ExposureTime.SetValue(28.0)
            cam.TriggerDelay.SetValue(0.0)

            with self._camera_lock:
                self._camera = cam

            cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            converter = pylon.ImageFormatConverter()
            converter.OutputPixelFormat = pylon.PixelType_BGR8packed

            while cam.IsGrabbing() and self._running:
                try:
                    grab = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
                    if grab.GrabSucceeded():
                        image = converter.Convert(grab)
                        img = image.GetArray()

                        # Resize for web display
                        target_w = 640
                        aspect = img.shape[0] / img.shape[1]
                        target_h = int(target_w * aspect)
                        img_resized = cv2.resize(img, (target_w, target_h))
                        ret, jpeg = cv2.imencode('.jpg', img_resized, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        if ret:
                            frame_bytes = jpeg.tobytes()
                            with self._frame_lock:
                                self._latest_frame_jpeg = frame_bytes
                            if self._recording:
                                self._record_frames.append(frame_bytes)
                    grab.Release()
                except pylon.GenericException as e:
                    logger.error("Pylon grab error: %s", e)
                    time.sleep(0.1)
                except Exception as e:
                    logger.error("Processing error: %s", e)
                    time.sleep(0.1)

        except pylon.GenericException as e:
            logger.error("Camera init error: %s", e)
            error_img = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(error_img, "Camera Error", (50, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            ret, jpeg = cv2.imencode('.jpg', error_img)
            if ret:
                with self._frame_lock:
                    self._latest_frame_jpeg = jpeg.tobytes()
        except Exception as e:
            logger.error("Unexpected error: %s", e)
        finally:
            with self._camera_lock:
                self._camera = None
            if cam:
                if cam.IsGrabbing():
                    cam.StopGrabbing()
                if cam.IsOpen():
                    cam.Close()
            logger.info("Camera released.")

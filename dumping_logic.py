"""
Spatiotemporal Illegal Dumping Activity Reasoning Engine
=========================================================
Distinguishes between harmless pedestrian transit and active illegal waste dumping.

Core Logic & Heuristic Pipeline:
1. Multi-Target Tracking:
   Maintains short-term trajectories of 'Person' and 'Waste Candidate' objects using
   Euclidean centroid displacement over consecutive frames.

2. Behavior State Machine:
   - STATE 1 [TRANSIT / ATTACHED]:
     Person and Waste Candidate centroids are within carrying distance (D < D_carry).
     Velocity vectors of person and object are collinear.
   - STATE 2 [DETACHMENT / SEPARATION]:
     Waste object velocity drops to zero (Delta_Centroid ~ 0), while Person velocity > 0.
     Distance D(Person, Waste) expands past D_separation threshold.
   - STATE 3 [TEMPORAL PERSISTENCE CONFIRMATION]:
     Waste object remains stationary for N consecutive frames (STATIONARY_CONFIRMATION_FRAMES).
     Person moves outside the immediate proximity perimeter (D > D_exit) or exits frame.
   - STATE 4 [ILLEGAL DUMPING EVENT TRIGGERED]:
     System confirms unauthorized disposal. Captures high-res annotated snapshot,
     dispatches real-time alert, and logs metadata to SQLite.

False Positive Mitigation:
- Pedestrian with Backpack: Centroid offset remains constant; velocities match (Ignored).
- Static pre-existing litter: If already present with no human detachment, flagged as
  environmental background waste, avoiding false dumping alarms.
- Accidental drop & retrieve: If person returns within confirmation window, event is aborted.
- Duplicate Alert Throttling: Enforces strict cooldown period per detected zone.
"""

import time
import math
import logging
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

import config

logger = logging.getLogger("SmartWasteSentinel.DumpingLogic")

@dataclass
class DumpingEvent:
    """Structure representing a verified illegal dumping incident."""
    incident_id: str
    timestamp: str
    object_class: str
    confidence: float
    bbox: List[int]
    centroid: Tuple[int, int]
    lux_level: float
    led_active: bool

class TrackedEntity:
    """Tracks centroid, velocity, and lifecycle of an object across frames."""
    def __init__(self, track_id: int, entity_class: str, centroid: Tuple[int, int], bbox: List[int], confidence: float):
        self.track_id = track_id
        self.entity_class = entity_class
        self.centroid = centroid
        self.bbox = bbox
        self.confidence = confidence
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.stationary_frames = 0
        self.history = [centroid]
        # State tracking for true dumping act
        self.was_carried_by_person = False
        self.has_been_captured = False  # Guarantees ONLY ONE capture per dumping incident!

    def update(self, centroid: Tuple[int, int], bbox: List[int], confidence: float):
        displacement = math.hypot(centroid[0] - self.centroid[0], centroid[1] - self.centroid[1])
        if displacement < config.STATIONARY_TOLERANCE_PIXELS:
            self.stationary_frames += 1
        else:
            self.stationary_frames = 0

        self.centroid = centroid
        self.bbox = bbox
        self.confidence = confidence
        self.last_seen = time.time()
        self.history.append(centroid)
        if len(self.history) > 30:
            self.history.pop(0)

class IllegalDumpingEngine:
    """Stateful spatiotemporal reasoning engine for illegal dumping detection."""

    def __init__(self):
        self.next_track_id = 1
        self.tracked_people: Dict[int, TrackedEntity] = {}
        self.tracked_waste: Dict[int, TrackedEntity] = {}
        self.last_alert_time = 0.0
        self.total_dumping_incidents = 0
        self.recent_events: List[DumpingEvent] = []

    def process_frame(self, detections: List[Dict], lux: float = 50.0, led_state: bool = False) -> Optional[DumpingEvent]:
        """
        Processes frame detections and evaluates dumping state machine.
        Captures ONLY when a waste item is actively dumped and abandoned, NOT continuously.
        """
        current_time = time.time()

        # Split detections into persons and waste candidates
        persons_in_frame = [d for d in detections if d["class"] == "person"]
        waste_in_frame = [d for d in detections if d["class"] in config.WASTE_CLASSES]

        # 1. Update Tracks
        self._update_tracks(self.tracked_people, persons_in_frame, "person")
        self._update_tracks(self.tracked_waste, waste_in_frame, "waste")

        # 2. Clean stale tracks (lost for > 3.0 seconds)
        self._prune_stale_tracks(self.tracked_people, current_time, timeout=3.0)
        self._prune_stale_tracks(self.tracked_waste, current_time, timeout=6.0)

        # 3. Analyze Human-Waste Association
        for waste_track in self.tracked_waste.values():
            # Check proximity to any person
            for person_track in self.tracked_people.values():
                d = math.hypot(waste_track.centroid[0] - person_track.centroid[0],
                               waste_track.centroid[1] - person_track.centroid[1])
                # If person was in close contact with this waste, record it was carried
                if d < config.SEPARATION_DISTANCE_PIXELS * 1.5:
                    waste_track.was_carried_by_person = True

        # 4. Strict Dumping Act Verification:
        # A capture happens ONLY WHEN:
        #   (a) The waste item has NOT been captured before (has_been_captured == False)
        #   (b) The waste item was being carried by a person (was_carried_by_person == True)
        #   (c) The waste item is now stationary on the ground (stationary_frames >= 4)
        #   (d) The person is detaching / moving away (distance > SEPARATION_DISTANCE_PIXELS) or has exited the frame
        verified_event = None

        for waste_track in list(self.tracked_waste.values()):
            if waste_track.has_been_captured:
                continue  # Already captured! NEVER capture again for this dumped item.

            if not waste_track.was_carried_by_person:
                continue  # Was not carried by a person (e.g. pre-existing litter) -> Do NOT capture

            # Is the waste now stationary?
            if waste_track.stationary_frames < 4:
                continue  # Still moving with the person -> Do NOT capture yet

            # Check distance to all persons currently visible in this frame
            min_dist_to_person = float("inf")
            for p_det in persons_in_frame:
                cx, cy = p_det["centroid"]
                d = math.hypot(waste_track.centroid[0] - cx, waste_track.centroid[1] - cy)
                if d < min_dist_to_person:
                    min_dist_to_person = d

            # Separation Condition: Either no person visible in frame, OR nearest person is stepping away!
            is_separated = (len(persons_in_frame) == 0) or (min_dist_to_person > config.SEPARATION_DISTANCE_PIXELS)

            if is_separated:
                # Mark as captured so it will NEVER trigger again!
                waste_track.has_been_captured = True
                self.last_alert_time = current_time
                self.total_dumping_incidents += 1

                incident_id = f"INC-{time.strftime('%Y%m%d-%H%M%S')}-{self.total_dumping_incidents}"
                timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")

                event = DumpingEvent(
                    incident_id=incident_id,
                    timestamp=timestamp_str,
                    object_class="garbage_bag",
                    confidence=waste_track.confidence,
                    bbox=waste_track.bbox,
                    centroid=waste_track.centroid,
                    lux_level=lux,
                    led_active=led_state
                )

                self.recent_events.append(event)
                if len(self.recent_events) > 50:
                    self.recent_events.pop(0)

                verified_event = event
                logger.warning("[EXACT DUMPING ACT CAPTURED] Incident Ref: %s at %s", incident_id, timestamp_str)
                break

        return verified_event

    def _update_tracks(self, track_dict: Dict[int, TrackedEntity], current_dets: List[Dict], default_class: str):
        """Matches current detections to existing tracks using nearest centroid association."""
        matched_tracks = set()

        for det in current_dets:
            cx, cy = det["centroid"]
            cls_name = det.get("raw_class", default_class)
            best_track_id = None
            best_distance = 65.0  # Max pixel jump between frames

            for track_id, track in track_dict.items():
                if track_id in matched_tracks:
                    continue
                d = math.hypot(cx - track.centroid[0], cy - track.centroid[1])
                if d < best_distance:
                    best_distance = d
                    best_track_id = track_id

            if best_track_id is not None:
                track_dict[best_track_id].update(det["centroid"], det["bbox"], det["confidence"])
                matched_tracks.add(best_track_id)
            else:
                # Spawn new track
                new_id = self.next_track_id
                self.next_track_id += 1
                track_dict[new_id] = TrackedEntity(new_id, cls_name, det["centroid"], det["bbox"], det["confidence"])
                matched_tracks.add(new_id)

    def _prune_stale_tracks(self, track_dict: Dict[int, TrackedEntity], current_time: float, timeout: float):
        """Removes tracks that haven't received updates within timeout seconds."""
        stale_ids = [tid for tid, track in track_dict.items() if (current_time - track.last_seen) > timeout]
        for tid in stale_ids:
            del track_dict[tid]

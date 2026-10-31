"""
Hazard Analyzer for AI Vision Assistant (2026 SOTA)
Implements Strict 'Silent-Until-Danger' Spatial Filtering:
- Center collision corridor prioritization
- Side encroachment threshold (Area_Ratio >= 0.12)
- Zero spoken chattering during clear paths
"""

from typing import List, Dict, Any, Optional
from backend.core.config import settings

class HazardAnalyzer:
    """
    Evaluates detected objects, computes spatial positioning across 3 corridors
    (Left, Center, Right), calculates proximity area ratios, and prioritizes
    critical voice alerts strictly when collision threat exists.
    """
    
    CRITICAL_HAZARDS = {
        "pothole", "manhole", "open manhole", "ditch", "unpaved ditch",
        "wire", "hanging wire", "electrical switchboard", "switchboard",
        "step", "steps", "stairs", "motorcycle", "car", "truck", "bus",
        "barrier", "pole", "curb", "ground drop-off", "hole"
    }

    # Benign objects that should never trigger navigation alerts
    BENIGN_OBJECTS = {
        "laptop", "cell phone", "phone", "cup", "bottle", "book", "mouse",
        "keyboard", "remote", "clock", "vase", "bowl", "tv", "bed"
    }
    
    def __init__(self):
        self.last_alert_time = 0.0
        self.cooldown_sec = 6.0  # Strict 6s cooldown per hazard
        self.last_alert_key = ""

    def analyze(self, detections: List[Dict[str, Any]], frame_w: int, frame_h: int) -> Dict[str, Any]:
        """
        Input: list of detections, each:
          { 'label': str, 'conf': float, 'bbox': [x1, y1, x2, y2] }
        Output:
          {
            'objects': list of enhanced objects,
            'corridors': {'left': [...], 'center': [...], 'right': [...]},
            'priority_alert': Optional[str],
            'scene_description': str,
            'has_critical_hazard': bool
          }
        """
        frame_area = max(1, frame_w * frame_h)
        enhanced_objects = []
        corridors = {"left": [], "center": [], "right": []}
        critical_alerts = []
        has_critical = False

        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            box_w = max(0, x2 - x1)
            box_h = max(0, y2 - y1)
            box_area = box_w * box_h
            area_ratio = box_area / frame_area
            
            label = det["label"].strip().lower()
            conf = det["conf"]

            # Filter out benign desktop / indoor accessories
            if label in self.BENIGN_OBJECTS and area_ratio < 0.25:
                continue

            # Spatial corridor
            cx = (x1 + x2) / 2.0
            if cx < frame_w * settings.CORRIDOR_LEFT:
                corridor = "left"
            elif cx > frame_w * settings.CORRIDOR_RIGHT:
                corridor = "right"
            else:
                corridor = "center"
            
            # Proximity estimation
            if area_ratio >= settings.PROXIMITY_CRITICAL_RATIO:
                proximity = "very close"
            elif area_ratio >= settings.PROXIMITY_WARNING_RATIO:
                proximity = "close"
            elif area_ratio >= settings.PROXIMITY_FAR_RATIO:
                proximity = "nearby"
            else:
                proximity = "distant"
                
            # Check if critical physical hazard
            is_hazard = any(k in label for k in self.CRITICAL_HAZARDS)
            is_person = "person" in label or "human" in label

            obj_info = {
                "label": det["label"],
                "confidence": round(conf, 2),
                "bbox": [round(x1), round(y1), round(x2), round(y2)],
                "corridor": corridor,
                "area_ratio": round(area_ratio, 4),
                "proximity": proximity,
                "is_hazard": is_hazard or is_person,
                "is_critical": False
            }

            # Silent-Until-Danger Rule Evaluation:
            # 1. Threat in Center Corridor:
            if corridor == "center":
                if is_hazard or area_ratio >= 0.08:
                    obj_info["is_critical"] = True
                    has_critical = True
                    if is_hazard:
                        alert = f"Stop: {det['label']} close in center path."
                    elif is_person:
                        alert = "Caution: Person directly in your path."
                    else:
                        alert = f"Caution: Obstacle ahead in center path."
                    critical_alerts.append(alert)

            # 2. Side Encroachment Rule (Area_Ratio >= 0.12):
            elif area_ratio >= 0.12 and is_hazard:
                obj_info["is_critical"] = True
                has_critical = True
                critical_alerts.append(f"Caution: {det['label']} close on your {corridor}.")

            enhanced_objects.append(obj_info)
            corridors[corridor].append(obj_info)

        # Pick top priority alert (if any)
        top_alert = critical_alerts[0] if critical_alerts else None

        # Build natural scene description
        scene_description = self._synthesize_scene_description(corridors)

        return {
            "objects": enhanced_objects,
            "corridors": corridors,
            "priority_alert": top_alert,
            "scene_description": scene_description,
            "has_critical_hazard": has_critical
        }

    def _synthesize_scene_description(self, corridors: Dict[str, List[Dict[str, Any]]]) -> str:
        parts = []
        for side in ["center", "left", "right"]:
            items = corridors[side]
            if not items:
                continue
            counts: Dict[str, int] = {}
            for it in items:
                lbl = it["label"]
                counts[lbl] = counts.get(lbl, 0) + 1
            
            side_summary = []
            for name, count in counts.items():
                if count > 1:
                    side_summary.append(f"{count} {name}s")
                else:
                    side_summary.append(f"a {name}")
            
            side_text = ", ".join(side_summary)
            if side == "center":
                parts.append(f"Directly ahead: {side_text}")
            else:
                parts.append(f"On your {side}: {side_text}")
                
        if not parts:
            return "Clear path, no obstacles detected."
        return ". ".join(parts) + "."

hazard_analyzer = HazardAnalyzer()

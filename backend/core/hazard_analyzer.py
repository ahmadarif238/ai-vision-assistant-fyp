from typing import List, Dict, Any, Optional
from backend.core.config import settings

class HazardAnalyzer:
    """
    Evaluates detected objects, computes spatial positioning across 3 corridors
    (Left, Center, Right), calculates proximity area ratios, and prioritizes
    critical voice alerts for immediate safety.
    """
    
    HIGH_RISK_KEYWORDS = {
        "pothole", "manhole", "open manhole", "ditch", "unpaved ditch",
        "wire", "hanging wire", "electrical", "switchboard", "step", "stairs",
        "motorcycle", "car", "truck", "bus", "barrier", "pole", "curb"
    }
    
    def __init__(self):
        self.last_alert_time = 0.0
        self.cooldown_sec = 2.0  # Avoid repetitive spamming of identical alerts
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
                is_critical = True
            elif area_ratio >= settings.PROXIMITY_WARNING_RATIO:
                proximity = "approaching"
                is_critical = False
            elif area_ratio >= settings.PROXIMITY_FAR_RATIO:
                proximity = "nearby"
                is_critical = False
            else:
                proximity = "distant"
                is_critical = False
                
            label = det["label"]
            conf = det["conf"]
            
            # Check if high hazard
            is_hazard = any(k in label.lower() for k in self.HIGH_RISK_KEYWORDS)
            
            obj_info = {
                "label": label,
                "confidence": round(conf, 2),
                "bbox": [round(x1), round(y1), round(x2), round(y2)],
                "corridor": corridor,
                "area_ratio": round(area_ratio, 4),
                "proximity": proximity,
                "is_hazard": is_hazard,
                "is_critical": is_critical
            }
            enhanced_objects.append(obj_info)
            corridors[corridor].append(obj_info)
            
            # Evaluate priority alert
            if is_critical and corridor == "center":
                has_critical = True
                alert_text = f"Stop! {label} very close in center!" if is_hazard else f"Caution: {label} directly ahead!"
                critical_alerts.append(alert_text)
            elif is_hazard and is_critical:
                has_critical = True
                critical_alerts.append(f"Caution: {label} on the {corridor} very close!")
            elif is_hazard and proximity == "approaching" and corridor == "center":
                critical_alerts.append(f"Attention: {label} approaching in center.")

        # Pick top priority alert
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
            # Summarize items on this side
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


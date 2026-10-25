"""Reproducible LA solar position and lighting-presets preparation.

Astronomical positions are computed, while lighting intensities and sky settings
are authored rendering choices.  No weather observation or photometry is implied.
Blender reads the resulting JSON and does not need pyproj installed internally.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("America/Los_Angeles")
RAD = math.pi / 180.0


def local_time(value: str, fold: int = 0) -> datetime:
    """Interpret a wall time in LA, rejecting spring-forward nonexistent times."""
    wall = datetime.fromisoformat(value)
    if wall.tzinfo is not None:
        raise ValueError("Give a local wall time without an offset; timezone is recorded separately")
    aware = wall.replace(tzinfo=TZ, fold=fold)
    if aware.astimezone(timezone.utc).astimezone(TZ).replace(tzinfo=None) != wall:
        raise ValueError("Nonexistent America/Los_Angeles wall time")
    return aware


def solar_position(local_datetime: str, latitude: float, longitude: float, fold: int = 0) -> dict:
    """NOAA/Meeus solar equations, true-north azimuth clockwise, degrees.

    Reference equations: https://gml.noaa.gov/grad/solcalc/calcdetails.html
    The geometric altitude excludes atmospheric refraction.  The optional NOAA
    apparent-altitude approximation assumes standard atmosphere, not LA weather.
    """
    when = local_time(local_datetime, fold)
    utc = when.astimezone(timezone.utc)
    jd = utc.timestamp() / 86400.0 + 2440587.5
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    mean_anomaly = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    eccentricity = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    centre = (math.sin(mean_anomaly * RAD) * (1.914602 - t * (0.004817 + 0.000014 * t))
              + math.sin(2 * mean_anomaly * RAD) * (0.019993 - 0.000101 * t)
              + math.sin(3 * mean_anomaly * RAD) * 0.000289)
    true_longitude = l0 + centre
    omega = 125.04 - 1934.136 * t
    apparent_longitude = true_longitude - 0.00569 - 0.00478 * math.sin(omega * RAD)
    mean_obliquity = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    obliquity = mean_obliquity + 0.00256 * math.cos(omega * RAD)
    declination = math.asin(math.sin(obliquity * RAD) * math.sin(apparent_longitude * RAD))
    y = math.tan(obliquity * RAD / 2) ** 2
    equation_minutes = 4 / RAD * (
        y * math.sin(2 * l0 * RAD) - 2 * eccentricity * math.sin(mean_anomaly * RAD)
        + 4 * eccentricity * y * math.sin(mean_anomaly * RAD) * math.cos(2 * l0 * RAD)
        - 0.5 * y * y * math.sin(4 * l0 * RAD)
        - 1.25 * eccentricity * eccentricity * math.sin(2 * mean_anomaly * RAD))
    utc_minutes = utc.hour * 60 + utc.minute + (utc.second + utc.microsecond / 1e6) / 60
    true_solar_minutes = (utc_minutes + equation_minutes + 4 * longitude) % 1440
    hour_angle = (true_solar_minutes / 4 - 180) * RAD
    lat = latitude * RAD
    sine_altitude = (math.sin(lat) * math.sin(declination)
                    + math.cos(lat) * math.cos(declination) * math.cos(hour_angle))
    altitude = math.asin(max(-1, min(1, sine_altitude))) / RAD
    azimuth = (math.atan2(math.sin(hour_angle),
                         math.cos(hour_angle) * math.sin(lat)
                         - math.tan(declination) * math.cos(lat)) / RAD + 180) % 360
    # NOAA's piecewise refraction correction is an approximation, not measured.
    if altitude > 85:
        refraction_arcsec = 0.0
    elif altitude > 5:
        tangent = math.tan(altitude * RAD)
        refraction_arcsec = 58.1 / tangent - 0.07 / tangent**3 + 0.000086 / tangent**5
    elif altitude > -0.575:
        refraction_arcsec = 1735 + altitude * (-518.2 + altitude * (103.4 + altitude * (-12.79 + altitude * 0.711)))
    else:
        refraction_arcsec = -20.772 / math.tan(altitude * RAD)
    return {
        "local_datetime": when.isoformat(), "wall_time": local_datetime,
        "timezone": "America/Los_Angeles", "fold": fold,
        "utc_datetime": utc.isoformat(), "utc_offset_hours": when.utcoffset().total_seconds() / 3600,
        "julian_date_utc": jd, "latitude_deg": latitude, "longitude_deg": longitude,
        "azimuth_true_north_clockwise_deg": azimuth,
        "altitude_geometric_deg": altitude,
        "altitude_apparent_standard_atmosphere_deg": altitude + refraction_arcsec / 3600,
        "declination_deg": declination / RAD, "equation_of_time_minutes": equation_minutes,
        "hour_angle_deg": hour_angle / RAD,
    }


def solar_vector(azimuth_deg: float, altitude_deg: float) -> list[float]:
    az, alt = azimuth_deg * RAD, altitude_deg * RAD
    return [math.cos(alt) * math.sin(az), math.cos(alt) * math.cos(az), math.sin(alt)]


def angular_distance(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def independent_sidereal_check(record: dict) -> dict:
    """Independent RA/sidereal rotation path for a calculation consistency check.

    This is a lower-order orbital model, not an independent measured ephemeris.
    Its agreement must never be reported as source survey/photometric accuracy.
    """
    jd = record["julian_date_utc"]
    n = jd - 2451545.0
    mean_long = (280.460 + 0.9856474 * n) % 360
    anomaly = (357.528 + 0.9856003 * n) * RAD
    longitude = (mean_long + 1.915 * math.sin(anomaly) + 0.020 * math.sin(2 * anomaly)) * RAD
    epsilon = (23.439 - 0.0000004 * n) * RAD
    right_ascension = math.atan2(math.cos(epsilon) * math.sin(longitude), math.cos(longitude)) / RAD
    declination = math.asin(math.sin(epsilon) * math.sin(longitude))
    sidereal = (280.46061837 + 360.98564736629 * n) % 360
    hour = ((sidereal + record["longitude_deg"] - right_ascension + 180) % 360 - 180) * RAD
    lat = record["latitude_deg"] * RAD
    altitude = math.asin(math.sin(lat) * math.sin(declination)
                         + math.cos(lat) * math.cos(declination) * math.cos(hour)) / RAD
    azimuth = (math.atan2(math.sin(hour), math.cos(hour) * math.sin(lat)
                         - math.tan(declination) * math.cos(lat)) / RAD + 180) % 360
    return {
        "method": "low-order solar right-ascension / Greenwich sidereal-time path",
        "altitude_deg": altitude, "azimuth_deg": azimuth,
        "absolute_altitude_difference_deg": abs(altitude - record["altitude_geometric_deg"]),
        "absolute_azimuth_difference_deg": angular_distance(azimuth, record["azimuth_true_north_clockwise_deg"]),
        "meaning": "calculation consistency only; not an observed-sun or source-accuracy validation",
    }


def build_config(root: Path = ROOT) -> dict:
    # Project Python has pyproj locked; Blender consumes JSON only.
    from pyproj import Proj, Transformer
    origin = json.loads((root / "data/processed/origin.json").read_text())
    longitude, latitude = origin["origin_lon_lat"]
    convergence = Proj("EPSG:32611").get_factors(longitude, latitude).meridian_convergence
    transformer = Transformer.from_crs(4326, 32611, always_xy=True)
    x0, y0 = transformer.transform(longitude, latitude)
    x1, y1 = transformer.transform(longitude, latitude + 0.001)
    true_north_grid_azimuth = math.atan2(x1 - x0, y1 - y0) / RAD
    assert abs(true_north_grid_azimuth + convergence) < 0.0001
    authored = {
        "clear_day": {"wall_time": "2025-09-21T13:00:00", "label_zh": "晴朗白天",
                      "sun_energy": 3.0, "sun_color_linear_rgb": [1.0, 0.97, 0.91], "sun_angle_deg": 0.526,
                      "world_model": "nishita", "world_strength": 0.28, "exposure_stops": 0.0,
                      "artificial_lights_enabled": False},
        "golden_hour": {"wall_time": "2025-09-21T18:20:00", "label_zh": "日落前暖光",
                        "sun_energy": 1.8, "sun_color_linear_rgb": [1.0, 0.65, 0.35], "sun_angle_deg": 0.526,
                        "world_model": "nishita", "world_strength": 0.20, "exposure_stops": 0.2,
                        "artificial_lights_enabled": False},
        "blue_hour": {"wall_time": "2025-09-21T19:20:00", "label_zh": "蓝调时刻",
                      "sun_energy": 0.0, "sun_color_linear_rgb": [1.0, 0.5, 0.25], "sun_angle_deg": 0.526,
                      "world_model": "authored_twilight_constant", "world_color_linear_rgb": [0.075, 0.13, 0.28],
                      "world_strength": 0.32, "exposure_stops": 1.0, "artificial_lights_enabled": True},
        "night": {"wall_time": "2025-09-21T21:00:00", "label_zh": "夜景",
                  "sun_energy": 0.0, "sun_color_linear_rgb": [1.0, 0.5, 0.25], "sun_angle_deg": 0.526,
                  "world_model": "authored_night_constant", "world_color_linear_rgb": [0.04, 0.055, 0.10],
                  "world_strength": 0.10, "exposure_stops": 1.3, "artificial_lights_enabled": True},
    }
    records = {}
    checks = []
    for name, settings in authored.items():
        solar = solar_position(settings["wall_time"], latitude, longitude)
        az = (solar["azimuth_true_north_clockwise_deg"] - convergence) % 360
        alt = solar["altitude_geometric_deg"]
        vector = solar_vector(az, alt)
        # XYZ Euler: world +Z is toward the Sun; Blender SUN emits along -Z.
        euler = [90 - alt, 0.0, 180 - az]
        x, _, z = (q * RAD for q in euler)
        reconstructed = [math.sin(z) * math.sin(x), -math.cos(z) * math.sin(x), math.cos(x)]
        assert max(abs(a - b) for a, b in zip(vector, reconstructed)) < 1e-12
        independent = independent_sidereal_check(solar)
        assert independent["absolute_altitude_difference_deg"] < 0.05
        assert independent["absolute_azimuth_difference_deg"] < 0.05
        records[name] = settings | {
            "solar": solar, "azimuth_grid_north_clockwise_deg": az,
            "sun_direction_towards_sun_grid_xyz": vector,
            "sun_ray_direction_grid_xyz": [-v for v in vector],
            "sun_rotation_euler_xyz_degrees": euler,
            "solar_altitude_used_for_rotation": "geometric_no_refraction",
            "sun_below_horizon": alt < 0,
            "lighting_parameter_evidence": "authored plausible rendering parameters; not measured solar irradiance, sky luminance, or weather",
        }
        checks.append({"preset": name, "passed": True, "independent_comparison": independent,
                       "euler_vector_max_absolute_error": max(abs(a - b) for a, b in zip(vector, reconstructed))})
    assert 40 < records["clear_day"]["solar"]["altitude_geometric_deg"] < 70
    assert 0 < records["golden_hour"]["solar"]["altitude_geometric_deg"] < 10
    assert -12 < records["blue_hour"]["solar"]["altitude_geometric_deg"] < -6
    assert records["night"]["solar"]["altitude_geometric_deg"] < -18
    assert all(v["solar"]["utc_offset_hours"] == -7 for v in records.values())
    assert local_time("2025-01-15T12:00:00").utcoffset().total_seconds() / 3600 == -8
    assert local_time("2025-07-15T12:00:00").utcoffset().total_seconds() / 3600 == -7
    assert local_time("2025-11-02T01:30:00", 0).utcoffset().total_seconds() / 3600 == -7
    assert local_time("2025-11-02T01:30:00", 1).utcoffset().total_seconds() / 3600 == -8
    rejected = False
    try:
        local_time("2025-03-09T02:30:00")
    except ValueError:
        rejected = True
    assert rejected
    noon = min((solar_position(f"2025-09-21T{h:02d}:{m:02d}:00", latitude, longitude)
                for h in (12, 13) for m in range(60)), key=lambda r: abs(r["hour_angle_deg"]))
    assert angular_distance(noon["azimuth_true_north_clockwise_deg"], 180) < 0.3
    return {
        "stage": 8, "schema_version": 1, "prepared_before_stage07_acceptance": True,
        "reference_location": {"longitude_deg": longitude, "latitude_deg": latitude,
                               "origin_source": "data/processed/origin.json", "horizontal_crs": "EPSG:32611",
                               "axes": "X grid east, Y grid north, Z up; metres",
                               "meridian_convergence_deg": convergence,
                               "grid_azimuth_rule": "true azimuth minus meridian convergence",
                               "true_north_projected_grid_azimuth_deg": true_north_grid_azimuth},
        "solar_method": {
            "algorithm": "NOAA solar calculator / Meeus Julian-century equations",
            "reference_url": "https://gml.noaa.gov/grad/solcalc/calcdetails.html",
            "time_basis": "aware America/Los_Angeles converted to UTC; system timezone not used",
            "altitude": "geometric altitude drives Sun orientation; apparent standard-atmosphere estimate recorded separately",
            "accuracy": "analytical approximation; no observed Sun comparison, no weather or photometric calibration; not a survey-accuracy claim",
            "geographic_extent": "single Downtown reference Sun direction shared by city; no per-tile ephemeris required at this visual scale",
        },
        "presets": records,
        "validation": {"status": "passed", "actual_execution": True,
                       "comparisons": checks, "dst_winter_summer_and_fall_fold_passed": True,
                       "nonexistent_spring_time_rejected": True,
                       "projected_true_north_sign_verified": True,
                       "near_solar_noon": {"local_datetime": noon["local_datetime"],
                                           "azimuth_deg": noon["azimuth_true_north_clockwise_deg"],
                                           "altitude_deg": noon["altitude_geometric_deg"]},
                       "scope": "solar computation and transforms only; no stage08 model/render acceptance implied"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-config", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    config = build_config()
    path = ROOT / "config/stage08_lighting.json"
    if args.write_config:
        if path.exists():
            old = json.loads(path.read_text())
            if old != config:
                raise RuntimeError("Existing lighting config differs; preserve edits before regeneration")
        else:
            path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    if args.check:
        actual = json.loads(path.read_text())
        if actual != config:
            raise RuntimeError("Saved lighting parameters or calculated Sun positions differ from reproducible inputs")
    print(json.dumps({"status": "passed", "configuration_written": args.write_config,
                      "saved_configuration_checked": args.check,
                      "presets": {name: {"local": r["solar"]["local_datetime"],
                                           "altitude_geometric_deg": r["solar"]["altitude_geometric_deg"],
                                           "azimuth_true_deg": r["solar"]["azimuth_true_north_clockwise_deg"],
                                           "azimuth_grid_deg": r["azimuth_grid_north_clockwise_deg"]}
                                  for name, r in config["presets"].items()},
                      "validation": config["validation"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

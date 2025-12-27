from math import radians, cos, sin, asin, sqrt
from typing import List, Literal, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging
from backend.services.router_manager import router_manager
from backend.services.osrm import OSRMClient
from backend.services.mapbox_geocoding import MapboxGeocoder
from backend.config import routing_config

logger = logging.getLogger(__name__)
# Using router_manager for unified routing across all providers
# osrm_client kept for backward compatibility in some endpoints
osrm_client = OSRMClient()
# Initialize Mapbox geocoder for global location support
mapbox_geocoder = MapboxGeocoder(routing_config.mapbox_api_key)



router = APIRouter()


TravelMode = Literal["car", "bike", "walk", "transit"]


class Coordinate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class RouteLeg(BaseModel):
    start: Coordinate
    end: Coordinate
    distance_meters: float
    duration_seconds: float
    mode: TravelMode
    geometry: str = Field(
        default="",
        description="Encoded polyline string of the route path."
    )


class RouteSummary(BaseModel):
    distance_meters: float
    duration_seconds: float
    estimated_co2_kg: float


class RouteRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    mode: TravelMode = "car"
    departure_time: Optional[str] = Field(
        default=None,
        description="ISO8601 timestamp, optional. Used for future real-time integrations.",
    )


class RouteResponse(BaseModel):
    waypoints: List[Coordinate]
    legs: List[RouteLeg]
    summary: RouteSummary
    debug: dict = Field(
        default_factory=dict,
        description="Extra hackathon-friendly debug info.",
    )


class AlternateRouteRequest(RouteRequest):
    event_type: str = Field(
        ...,
        description=(
            "Type of mobility event to consider when suggesting alternates, "
            "e.g. 'road_closure', 'protest', 'concert'."
        ),
    )


class AlternateRouteResponse(BaseModel):
    base_route: RouteResponse
    alternate_route: RouteResponse
    reasoning: str = Field(
        ...,
        description="Human-readable explanation of how events influenced the suggestion.",
    )


def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Simple haversine implementation to approximate distance in meters.

    This keeps the demo self-contained without needing external routing APIs.
    """
    r = 6371000  # Earth radius in meters

    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return r * c


def _estimate_speed_mps(mode: TravelMode) -> float:
    if mode == "walk":
        return 1.4  # ~5 km/h
    if mode == "bike":
        return 4.1  # ~15 km/h
    if mode == "transit":
        return 8.3  # ~30 km/h (averaged)
    return 13.9  # car ~50 km/h urban average


def _estimate_co2_kg(distance_m: float, mode: TravelMode) -> float:
    # Very rough, illustrative values only (kg per km)
    if mode == "walk" or mode == "bike":
        return 0.0
    if mode == "transit":
        factor = 0.08
    else:  # car
        factor = 0.18
    return round((distance_m / 1000.0) * factor, 3)


@router.post("/plan", response_model=RouteResponse, summary="Plan a simple route")
async def plan_route(payload: RouteRequest) -> RouteResponse:
    """
    Plan a simple, single-leg route between two coordinates.
    
    Tries to use MapMyIndia Live Traffic API.
    Falls back to haversine estimation if API is unavailable or fails.
    """
    # 1. Try MapMyIndia API
    mmi_resp = await mmi_client.get_route(
        payload.origin.lat, payload.origin.lon,
        payload.destination.lat, payload.destination.lon,
        payload.mode
    )

    if mmi_resp:
        try:
            # Attempt to parse MapMyIndia response
            # Note: Adjust parsing logic based on actual API response structure
            # This assumes a structure similar to OSRM/Mapbox/Google
            routes = mmi_resp.get("routes", [])
            if routes:
                route = routes[0]
                # Extract distance/duration (often in meters/seconds)
                distance_m = float(route.get("distance", 0))
                duration_s = float(route.get("duration", 0))
                geometry = route.get("geometry", "")
                
                leg = RouteLeg(
                    start=payload.origin,
                    end=payload.destination,
                    distance_meters=round(distance_m, 2),
                    duration_seconds=round(duration_s, 1),
                    mode=payload.mode,
                    geometry=geometry,
                )

                summary = RouteSummary(
                    distance_meters=leg.distance_meters,
                    duration_seconds=leg.duration_seconds,
                    estimated_co2_kg=_estimate_co2_kg(distance_m, payload.mode),
                )

                return RouteResponse(
                    waypoints=[payload.origin, payload.destination],
                    legs=[leg],
                    summary=summary,
                    debug={
                        "implementation": "mapmyindia_live",
                        "note": "Live traffic data used.",
                    },
                )
        except Exception as e:
            logger.error(f"Error parsing MapMyIndia response: {e}")
            # Fall through to fallback

    # 2. Fallback to Haversine
    distance_m = _haversine_distance_m(
        payload.origin.lat,
        payload.origin.lon,
        payload.destination.lat,
        payload.destination.lon,
    )

    speed_mps = _estimate_speed_mps(payload.mode)
    duration_s = distance_m / speed_mps if speed_mps > 0 else 0

    leg = RouteLeg(
        start=payload.origin,
        end=payload.destination,
        distance_meters=round(distance_m, 2),
        duration_seconds=round(duration_s, 1),
        mode=payload.mode,
        geometry="", # No geometry for fallback/haversine
    )

    summary = RouteSummary(
        distance_meters=leg.distance_meters,
        duration_seconds=leg.duration_seconds,
        estimated_co2_kg=_estimate_co2_kg(distance_m, payload.mode),
    )

    return RouteResponse(
        waypoints=[payload.origin, payload.destination],
        legs=[leg],
        summary=summary,
        debug={
            "implementation": "haversine_stub",
            "note": "Fallback used (API unavailable or failed).",
        },
    )


@router.post(
    "/plan/alternate",
    response_model=AlternateRouteResponse,
    summary="Suggest an alternate route based on event type (mocked)",
)
async def plan_alternate_route(
    payload: AlternateRouteRequest,
) -> AlternateRouteResponse:
    """
    Suggest an alternate route based on the type of mobility event.

    Since we don't call real map APIs here, we use simple, transparent
    mock logic:

    - First compute the base route exactly like `/plan`.
    - Then adjust distance and duration by a multiplier that depends
      on `event_type` to simulate detours or slower traffic.
    - We keep the same origin/destination waypoints but clearly explain
      the assumptions in the `reasoning` field.
    """
    base = await plan_route(payload)  # reuse existing logic

    # Mock impact factors by event type
    normalized = payload.event_type.lower().strip()
    if normalized in {"road_closure", "accident", "construction"}:
        factor = 1.3  # 30% longer detour
        reason = (
            "Road closures typically force a detour around the blocked segment, "
            "so we assume about 30% extra distance and time."
        )
    elif normalized in {"protest", "rally", "parade"}:
        factor = 1.2  # slower traffic, mild detour
        reason = (
            "Protests and rallies can slow traffic and partially block streets, "
            "so we assume around 20% extra distance and time."
        )
    elif normalized in {"concert", "sports", "event"}:
        factor = 1.15  # congestion near venue
        reason = (
            "Large events create localized congestion near the venue, so we "
            "assume a 15% increase in distance and travel time for a smarter route."
        )
    else:
        factor = 1.05  # small generic buffer
        reason = (
            "Unknown event type. We apply a small 5% buffer as a conservative "
            "detour estimate while keeping the route close to the base plan."
        )

    alt_distance = round(base.summary.distance_meters * factor, 2)
    alt_duration = round(base.summary.duration_seconds * factor, 1)

    alt_summary = RouteSummary(
        distance_meters=alt_distance,
        duration_seconds=alt_duration,
        estimated_co2_kg=_estimate_co2_kg(alt_distance, payload.mode),
    )

    alt_leg = RouteLeg(
        start=payload.origin,
        end=payload.destination,
        distance_meters=alt_distance,
        duration_seconds=alt_duration,
        mode=payload.mode,
    )

    alternate = RouteResponse(
        waypoints=base.waypoints,
        legs=[alt_leg],
        summary=alt_summary,
        debug={
            "implementation": "event_type_multiplier_stub",
            "event_type": payload.event_type,
            "multiplier": factor,
        },
    )

    return AlternateRouteResponse(
        base_route=base,
        alternate_route=alternate,
        reasoning=reason,
    )


# ============================================================================
# Text-based location routing endpoint
# ============================================================================

class TextRouteRequest(BaseModel):
    source: str = Field(..., description="Starting location name (e.g., 'BTM Layout')")
    destination: str = Field(..., description="Destination location name (e.g., 'MG Road')")
    event: str = Field(
        default="",
        description="Event affecting the route (e.g., 'Political Rally', 'Road Closure')",
    )
    mode: TravelMode = Field(default="car", description="Travel mode: car, bike, walk, or transit")


class TextRouteResponse(BaseModel):
    recommended_route: str = Field(
        ...,
        description="Human-readable route description with waypoints",
    )
    reason: str = Field(
        ...,
        description="Explanation of why this route was recommended",
    )
    distance_meters: float = Field(..., description="Total distance in meters")
    distance_km: float = Field(..., description="Total distance in kilometers")
    duration_seconds: float = Field(..., description="Estimated travel time in seconds")
    duration_minutes: float = Field(..., description="Estimated travel time in minutes")
    estimated_co2_kg: float = Field(..., description="Estimated CO2 emissions in kg")
    waypoints: List[str] = Field(
        ...,
        description="List of waypoint names in order",
    )
    geometry: str = Field(
        default="",
        description="Encoded polyline of the route"
    )
    detailed_geometry: List[List[float]] = Field(
        default_factory=list,
        description="List of [lat, lon] coordinates for the route path"
    )
    steps: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Turn-by-turn directions"
    )
    start_point: Optional[Dict[str, Any]] = None
    end_point: Optional[Dict[str, Any]] = None


# Mock geocoding database for Bangalore locations
# In production, replace this with a real geocoding service (Google Maps, OSM Nominatim, etc.)
LOCATION_DB: Dict[str, Dict[str, float]] = {
    "btm layout": {"lat": 12.9166, "lon": 77.6101, "display": "BTM Layout"},
    "mg road": {"lat": 12.9716, "lon": 77.5946, "display": "MG Road"},
    "jp nagar": {"lat": 12.9067, "lon": 77.5858, "display": "JP Nagar"},
    "richmond road": {"lat": 12.9500, "lon": 77.6000, "display": "Richmond Road"},
    "lalbagh": {"lat": 12.9507, "lon": 77.5848, "display": "Lalbagh"},
    "indiranagar": {"lat": 12.9784, "lon": 77.6408, "display": "Indiranagar"},
    "koramangala": {"lat": 12.9352, "lon": 77.6245, "display": "Koramangala"},
    "whitefield": {"lat": 12.9698, "lon": 77.7499, "display": "Whitefield"},
    "marathahalli": {"lat": 12.9592, "lon": 77.6974, "display": "Marathahalli"},
    "hebbal": {"lat": 13.0358, "lon": 77.5970, "display": "Hebbal"},
    "electronic city": {"lat": 12.8456, "lon": 77.6633, "display": "Electronic City"},
    "cubbon park": {"lat": 12.9716, "lon": 77.5946, "display": "Cubbon Park"},
    "ulsoor": {"lat": 12.9784, "lon": 77.6408, "display": "Ulsoor"},
    "malleshwaram": {"lat": 13.0050, "lon": 77.5610, "display": "Malleshwaram"},
    "rajajinagar": {"lat": 12.9784, "lon": 77.5510, "display": "Rajajinagar"},
}


async def _geocode_location(location_name: str) -> Dict[str, float]:
    """
    Geocode a location name to coordinates.
    
    Strategy:
    1. Try local database first (fast, for known Bangalore locations)
    2. If not found, use Mapbox Geocoding API (global coverage)
    3. If Mapbox fails, fall back to Bangalore center
    """
    normalized = location_name.lower().strip()
    
    # Try local database first (fast lookup for known locations)
    # Direct match
    if normalized in LOCATION_DB:
        logger.debug(f"Found '{location_name}' in local database")
        return LOCATION_DB[normalized]
    
    # Partial match (e.g., "BTM" matches "BTM Layout")
    for key, value in LOCATION_DB.items():
        if normalized in key or key in normalized:
            logger.debug(f"Partial match for '{location_name}' in local database")
            return value
    
    # Not in local database - try Mapbox Geocoding API
    logger.info(f"Location '{location_name}' not in database, using Mapbox Geocoding")
    
    if mapbox_geocoder.is_configured:
        try:
            # Use async geocoding
            import asyncio
            result = await mapbox_geocoder.geocode(location_name, country="in")
            
            if result:
                logger.info(f"Successfully geocoded '{location_name}' via Mapbox")
                return result
            else:
                logger.warning(f"Mapbox could not geocode '{location_name}'")
        except Exception as e:
            logger.error(f"Error during Mapbox geocoding: {e}")
    else:
        logger.warning("Mapbox geocoder not configured, cannot geocode unknown location")
    
    # Final fallback: use central Bangalore coordinate
    logger.warning(f"Falling back to Bangalore center for '{location_name}'")
    return {"lat": 12.9716, "lon": 77.5946, "display": location_name.title()}


def _generate_waypoints(
    source: str, destination: str, event: str
) -> tuple[List[str], str, List[Dict[str, float]]]:
    """
    Generate realistic waypoints and intermediate coordinates based on source, destination, and event.
    Returns: (list of waypoint names, reasoning, list of intermediate coordinates)
    """
    source_norm = source.lower().strip()
    dest_norm = destination.lower().strip()
    event_norm = event.lower().strip()
    
    waypoints = [source]
    # Intermediate coords for road-following "illusion"
    intermediates = []
    
    # Common Junctions coordinates for Bangalore
    JUNCTIONS = {
        "Silk Board": {"lat": 12.9176, "lon": 77.6233, "display": "Silk Board Junction"},
        "Dairy Circle": {"lat": 12.9385, "lon": 77.6015, "display": "Dairy Circle"},
        "Richmond Circle": {"lat": 12.9600, "lon": 77.5969, "display": "Richmond Circle"},
        "Sony World": {"lat": 12.9352, "lon": 77.6245, "display": "Sony World Junction"},
        "Tin Factory": {"lat": 12.9940, "lon": 77.6800, "display": "Tin Factory"},
    }

    # Generate route based on known location combinations
    if "btm" in source_norm and "mg road" in dest_norm:
        if "rally" in event_norm or "protest" in event_norm or "lalbagh" in event_norm:
            # Detour via Dairy Circle and Richmond Circle
            waypoints.extend(["Dairy Circle", "Richmond Road"])
            intermediates = [JUNCTIONS["Dairy Circle"], JUNCTIONS["Richmond Circle"]]
            reason = "Avoiding rally congestion near Lalbagh via Dairy Circle"
        else:
            # Standard via Richmond Circle
            waypoints.extend(["Richmond Road"])
            intermediates = [JUNCTIONS["Richmond Circle"]]
            reason = "Optimal route via Richmond Circle"
    
    elif "btm" in source_norm and "koramangala" in dest_norm:
        waypoints.extend(["Sony World Junction"])
        intermediates = [JUNCTIONS["Sony World"]]
        reason = "Direct route via Sony World Junction"
    
    elif "whitefield" in source_norm and "mg road" in dest_norm:
        waypoints.extend(["Tin Factory", "Indiranagar"])
        intermediates = [JUNCTIONS["Tin Factory"]]
        reason = "Standard route via Tin Factory and Old Madras Road"
    
    elif "electronic city" in source_norm and "mg road" in dest_norm:
        waypoints.extend(["Silk Board", "Dairy Circle"])
        intermediates = [JUNCTIONS["Silk Board"], JUNCTIONS["Dairy Circle"]]
        reason = "Route via Silk Board and Dairy Circle"
    
    else:
        # Generic route generation
        if event_norm:
            waypoints.append("Alternate Connection")
            reason = f"Avoiding {event} by taking alternate route"
        else:
            waypoints.append("Direct Connection")
            reason = "Standard route recommendation"
    
    waypoints.append(destination)
    return waypoints, reason, intermediates


@router.post(
    "/suggest",
    response_model=TextRouteResponse,
    summary="Get route suggestion using text-based locations",
)
async def suggest_text_route(payload: TextRouteRequest) -> TextRouteResponse:
    """
    Suggest a route between two text-based locations (e.g., "BTM Layout" to "MG Road").
    
    This endpoint:
    - Accepts location names as strings (not coordinates)
    - Considers events that might affect routing
    - Returns a human-readable route description with waypoints
    - Includes distance, duration, and CO2 estimates
    
    Example request:
    ```json
    {
      "source": "BTM Layout",
      "destination": "MG Road",
      "event": "Political Rally"
    }
    ```
    
    Example response:
    ```json
    {
      "recommended_route": "BTM Layout → JP Nagar → Richmond Road → MG Road",
      "reason": "Avoiding rally congestion near Lalbagh",
      "distance_meters": 6500.0,
      "distance_km": 6.5,
      "duration_seconds": 468.0,
      "duration_minutes": 7.8,
      "estimated_co2_kg": 1.17,
      "waypoints": ["BTM Layout", "JP Nagar", "Richmond Road", "MG Road"]
    }
    ```
    """
    # Geocode source and destination (now using Mapbox for global coverage)
    source_coords = await _geocode_location(payload.source)
    dest_coords = await _geocode_location(payload.destination)
    
    # Generate waypoints, reasoning and intermediate points
    waypoints, reason, intermediate_points = _generate_waypoints(
        source_coords.get("display", payload.source),
        dest_coords.get("display", payload.destination),
        payload.event,
    )
    
    # Calculate distance using haversine
    distance_m = _haversine_distance_m(
        source_coords["lat"],
        source_coords["lon"],
        dest_coords["lat"],
        dest_coords["lon"],
    )
    
    # Apply event-based multiplier if event is specified
    if payload.event:
        event_norm = payload.event.lower().strip()
        if any(x in event_norm for x in ["rally", "protest", "parade", "political"]):
            distance_m *= 1.2  # 20% longer due to detour
            reason = f"Avoiding {payload.event.lower()} congestion"
        elif any(x in event_norm for x in ["closure", "accident", "construction"]):
            distance_m *= 1.3  # 30% longer due to detour
            reason = f"Detouring around {payload.event.lower()}"
        elif any(x in event_norm for x in ["concert", "sports", "event"]):
            distance_m *= 1.15  # 15% longer due to congestion
            reason = f"Avoiding {payload.event.lower()} traffic"
    
    # Calculate duration
    speed_mps = _estimate_speed_mps(payload.mode)
    duration_s = distance_m / speed_mps if speed_mps > 0 else 0
    
    # Calculate CO2
    co2_kg = _estimate_co2_kg(distance_m, payload.mode)

    # Use router_manager to get route with automatic provider fallback
    geometry = ""
    detailed_geometry = []
    steps = []
    provider_used = "fallback"
    
    try:
        # Router manager will try providers in order: preferred -> configured -> OSRM
        route_resp = await router_manager.get_route(
            source_coords["lat"], source_coords["lon"],
            dest_coords["lat"], dest_coords["lon"],
            payload.mode
        )
        
        if route_resp and route_resp.get("routes"):
            route = route_resp["routes"][0]
            geometry = route.get("geometry", "")
            
            # Update distance and duration from actual routing API
            distance_m = float(route.get("distance", distance_m))
            duration_s = float(route.get("duration", duration_s))
            
            # Extract steps
            legs = route.get("legs", [])
            for leg in legs:
                steps.extend(leg.get("steps", []))
            
            # Track which provider was used
            provider_used = route_resp.get("_provider_used", "unknown")
            logger.info(f"Route calculated using provider: {provider_used}")
            
    except Exception as e:
        logger.error(f"Routing API error in suggest_text_route: {e}")
        pass  # Fallback to mock steps below

    
    # Fallback: If no geometry from MMI, build a path and mock steps
    if not geometry:
        detailed_geometry.append([source_coords["lat"], source_coords["lon"]])
        # Start Step
        steps.append({
            "instruction": f"Start from {waypoints[0]}",
            "distance": 0,
            "duration": 0,
            "maneuver": {"location": [source_coords["lon"], source_coords["lat"]], "instruction": f"Start from {waypoints[0]}"}
        })
        
        for i, pt in enumerate(intermediate_points):
            detailed_geometry.append([pt["lat"], pt["lon"]])
            steps.append({
                "instruction": f"Head toward {pt['display']}",
                "distance": 500, # Mock distance
                "duration": 60,  # Mock duration
                "maneuver": {"location": [pt["lon"], pt["lat"]], "instruction": f"Pass through {pt['display']}"}
            })
            
        detailed_geometry.append([dest_coords["lat"], dest_coords["lon"]])
        # End Step
        steps.append({
            "instruction": f"Arrive at {waypoints[-1]}",
            "distance": 200,
            "duration": 30,
            "maneuver": {"location": [dest_coords["lon"], dest_coords["lat"]], "instruction": f"Arrive at {waypoints[-1]}"}
        })
    
    # Format route string
    route_str = " → ".join(waypoints)
    
    return TextRouteResponse(
        recommended_route=route_str,
        reason=reason,
        distance_meters=round(distance_m, 2),
        distance_km=round(distance_m / 1000.0, 2),
        duration_seconds=round(duration_s, 1),
        duration_minutes=round(duration_s / 60.0, 1),
        estimated_co2_kg=co2_kg,
        waypoints=waypoints,
        geometry=geometry,
        detailed_geometry=detailed_geometry,
        steps=steps,
        start_point=source_coords,
        end_point=dest_coords
    )

@router.post(
    "/recalculate",
    response_model=TextRouteResponse,
    summary="Recalculate route based on current coordinates and new event data",
)
async def recalculate_route(payload: TextRouteRequest) -> TextRouteResponse:
    """
    Simulates a dynamic recalculation. 
    In a real system, this might be triggered by a geofence or traffic event.
    """
    return await suggest_text_route(payload)


@router.get(
    "/providers/status",
    summary="Get routing provider configuration status",
)
async def get_provider_status() -> Dict[str, Any]:
    """
    Get status of all routing providers for debugging and monitoring.
    
    Returns information about:
    - Which providers are configured (have valid API keys)
    - Preferred provider setting
    - Fallback chain order
    - Provider requirements
    
    This endpoint is useful for:
    - Verifying API key configuration
    - Debugging routing issues
    - Monitoring provider availability
    
    Note: API keys are NEVER exposed in the response.
    """
    return router_manager.get_provider_status()

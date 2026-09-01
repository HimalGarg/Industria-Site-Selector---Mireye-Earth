import asyncio, httpx

async def test():
    # Census Geocoder
    url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    params = {
        "address": "9016 S Halsted St, Chicago, IL 60620",
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json"
    }
    async with httpx.AsyncClient() as c:
        r = await c.get(url, params=params)
        data = r.json()
        match = data.get("result", {}).get("addressMatches", [])[0]
        geos = match.get("geographies", {})
        counties = geos.get("Counties", [])
        states = geos.get("States", [])
        print("County:", counties[0]["NAME"] if counties else "None")
        print("State:", states[0]["STUSAB"] if states else "None")

    # USGS API
    usgs_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    usgs_params = {
        "format": "geojson",
        "latitude": "34.0522",
        "longitude": "-118.2437",
        "maxradiuskm": "50",
        "minmagnitude": "3.5",
        "limit": "5"
    }
    async with httpx.AsyncClient() as c:
        r = await c.get(usgs_url, params=usgs_params)
        print("USGS Status:", r.status_code)
        if r.status_code == 200:
            print("USGS Events:", len(r.json().get("features", [])))

    # FEMA API
    fema_url = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
    fema_params = {
        "$filter": "state eq 'CA' and designatedArea eq 'Los Angeles (County)'",
        "$top": "5",
        "$orderby": "declarationDate desc"
    }
    async with httpx.AsyncClient() as c:
        r = await c.get(fema_url, params=fema_params)
        print("FEMA Status:", r.status_code)
        if r.status_code == 200:
            print("FEMA Events:", len(r.json().get("DisasterDeclarationsSummaries", [])))

asyncio.run(test())

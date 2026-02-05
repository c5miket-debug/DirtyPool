#!/usr/bin/env python3
"""Weather for Yulee, FL via Open-Meteo (no API key).

Outputs JSON:
{
  "current": {"temp_f": 72.3, "wind_mph": 5.1, "code": 0, "time": "..."},
  "daily": [
     {"date":"2026-02-01","tmax_f":..,"tmin_f":..,"code":..,"precip_in":..}, ... up to days
  ]
}
"""

import argparse
import json
import ssl
import urllib.parse
import urllib.request

LAT, LON = 30.6319, -81.60649  # Yulee, FL

WMO = {
  0:"Clear",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
  45:"Fog",48:"Depositing rime fog",
  51:"Light drizzle",53:"Drizzle",55:"Dense drizzle",
  56:"Freezing drizzle",57:"Dense freezing drizzle",
  61:"Slight rain",63:"Rain",65:"Heavy rain",
  66:"Freezing rain",67:"Heavy freezing rain",
  71:"Slight snow",73:"Snow",75:"Heavy snow",
  77:"Snow grains",
  80:"Rain showers",81:"Rain showers",82:"Violent rain showers",
  85:"Snow showers",86:"Heavy snow showers",
  95:"Thunderstorm",96:"Thunderstorm w/ hail",99:"Thunderstorm w/ hail",
}

def fetch_json(url: str):
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(url, context=ctx, timeout=30) as r:
        return json.loads(r.read().decode('utf-8','ignore'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=5)
    ap.add_argument('--tz', default='America/New_York')
    args = ap.parse_args()

    daily_fields = [
        'temperature_2m_max','temperature_2m_min',
        'precipitation_sum','weathercode'
    ]
    current_fields = ['temperature_2m','weathercode','windspeed_10m']

    q = {
        'latitude': LAT,
        'longitude': LON,
        'timezone': args.tz,
        'temperature_unit': 'fahrenheit',
        'windspeed_unit': 'mph',
        'precipitation_unit': 'inch',
        'forecast_days': str(args.days),
        'current_weather': 'true',
        'daily': ','.join(daily_fields),
        'hourly': ','.join(current_fields),
    }
    url = 'https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q)
    data = fetch_json(url)

    out = {
        'current': {
            'time': (data.get('current_weather') or {}).get('time'),
            'temp_f': (data.get('current_weather') or {}).get('temperature'),
            'wind_mph': (data.get('current_weather') or {}).get('windspeed'),
            'code': (data.get('current_weather') or {}).get('weathercode'),
            'summary': WMO.get((data.get('current_weather') or {}).get('weathercode'), 'Unknown')
        },
        'daily': []
    }

    daily = data.get('daily') or {}
    times = daily.get('time') or []
    tmax = daily.get('temperature_2m_max') or []
    tmin = daily.get('temperature_2m_min') or []
    precip = daily.get('precipitation_sum') or []
    codes = daily.get('weathercode') or []

    for i, day in enumerate(times):
        out['daily'].append({
            'date': day,
            'tmax_f': tmax[i] if i < len(tmax) else None,
            'tmin_f': tmin[i] if i < len(tmin) else None,
            'precip_in': precip[i] if i < len(precip) else None,
            'code': codes[i] if i < len(codes) else None,
            'summary': WMO.get(codes[i], 'Unknown') if i < len(codes) else None,
        })

    print(json.dumps(out, indent=2))

if __name__ == '__main__':
    main()

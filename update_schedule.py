#!/usr/bin/env python3
"""Build a compact Israel Railways schedule index from the official MOT GTFS feed."""
import csv, io, json, re, urllib.request, zipfile, datetime, pathlib
from zoneinfo import ZoneInfo
URL='https://gtfs.mot.gov.il/gtfsfiles/israel-public-transportation.zip'
OUT=pathlib.Path(__file__).resolve().parent/'schedule.json'

def table(z,name):
    with z.open(name) as raw:
        return list(csv.DictReader(io.TextIOWrapper(raw,encoding='utf-8-sig')))

def main():
    req=urllib.request.Request(URL,headers={'User-Agent':'RailShiftPlanner/1.0'})
    with urllib.request.urlopen(req,timeout=120) as response:
        data=response.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        routes=table(z,'routes.txt'); agencies=table(z,'agency.txt'); stops=table(z,'stops.txt')
        railroutes={r['route_id']:r for r in routes if r.get('route_type')=='2'}
        # Train number is embedded in the published rail route short name in modern MOT GTFS.
        def train_no(r):
            name=r.get('route_short_name','')
            # e.g. 32086-1-651; use the last component only when the format is unambiguous.
            m=re.search(r'(?:^|[-/])([0-9]{2,6})$',name)
            return m.group(1) if m else (name if re.fullmatch(r'\d{2,6}',name) else None)
        route_numbers={rid:train_no(r) for rid,r in railroutes.items()}
        route_numbers={k:v for k,v in route_numbers.items() if v}
        trips={}
        for t in table(z,'trips.txt'):
            rid=t.get('route_id')
            if rid not in railroutes:continue
            # A rail number can be published on the trip rather than the route.
            # Prefer explicit trip_short_name, then an unambiguous route number.
            short=t.get('trip_short_name','').strip()
            number=short if re.fullmatch(r'[0-9]{2,6}',short) else route_numbers.get(rid)
            if number:trips[t['trip_id']]={'number':number,'service':t['service_id']}
        stopnames={r['stop_id']:r.get('stop_name','') for r in stops}
        calendars={r['service_id']:r for r in table(z,'calendar.txt')} if 'calendar.txt' in z.namelist() else {}
        exceptions={}
        if 'calendar_dates.txt' in z.namelist():
            for r in table(z,'calendar_dates.txt'):
                exceptions.setdefault(r['service_id'],{})[r['date']]=r['exception_type']
        today=datetime.datetime.now(ZoneInfo('Asia/Jerusalem')).date(); days=[today+datetime.timedelta(days=i) for i in range(11)]
        def runs(service,day):
            date=day.strftime('%Y%m%d')
            if date in exceptions.get(service,{}):return exceptions[service][date]=='1'
            c=calendars.get(service)
            return bool(c and c['start_date']<=date<=c['end_date'] and c[day.strftime('%A').lower()]=='1')
        active={t:{d.isoformat() for d in days if runs(meta['service'],d)} for t,meta in trips.items()}
        active={t:dates for t,dates in active.items() if dates}
        schedule={}
        # Stream large stop_times instead of holding the national feed in memory.
        with z.open('stop_times.txt') as raw:
            for r in csv.DictReader(io.TextIOWrapper(raw,encoding='utf-8-sig')):
                tid=r.get('trip_id')
                if tid not in active:continue
                schedule.setdefault(tid,[]).append([int(r['stop_sequence']),stopnames.get(r['stop_id'],r['stop_id']),r.get('arrival_time',''),r.get('departure_time','')])
        indexed={}
        for tid,st in schedule.items():
            st.sort(key=lambda a:a[0]); number=trips[tid]['number']
            for day in active[tid]:
                indexed.setdefault(day,{}).setdefault(number,[]).append({'stops':[x[1:] for x in st]})
        payload={'source':'משרד התחבורה — GTFS מתוכנן, לא פסיפס/RAILAPP','updated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'days':indexed,'warning':'נתוני תכנון ציבוריים; ייתכנו פערים מהסידור התפעולי.'}
        OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        print('wrote',OUT,'bytes',OUT.stat().st_size,'days',len(indexed),'rail routes',len(railroutes),'matched routes',len(route_numbers),'matched trips',len(trips),'test 651',any('651' in v for v in indexed.values()),'test 670',any('670' in v for v in indexed.values()))
if __name__=='__main__':main()

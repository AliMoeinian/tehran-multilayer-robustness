import pathlib,json,sqlite3,csv,struct,hashlib,datetime,shutil,zipfile,io,contextlib
import shapely,nbformat
R=pathlib.Path('outputs/tehran_dataset_v1_1');B=pathlib.Path('outputs/tehran_dataset_v1');s=json.loads((R/'enrichment_summary.json').read_text(encoding='utf8'))
def dump(name,obj):(R/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
def csvread(name):return list(csv.DictReader(open(R/name,encoding='utf-8-sig')))
parent=json.loads((B/'manifest.json').read_text(encoding='utf8'));expected=parent['files']['tehran_context.osm.pbf']['sha256']
assert hashlib.sha256((R/'tehran_context.osm.pbf').read_bytes()).hexdigest()==expected
assert hashlib.sha256((B/'tehran_context.osm.pbf').read_bytes()).hexdigest()==expected
db=sqlite3.connect('file:'+str(R/'tehran_audited_layers.gpkg')+'?mode=ro',uri=True);qa={}
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
for tab,declared in db.execute('SELECT table_name,geometry_type_name FROM gpkg_geometry_columns').fetchall():
 n=invalid=bad=0
 for (blob,) in db.execute(f'SELECT geom FROM {tab}'):
  n+=1
  if blob[:4]!=b'GP\x00\x03' or struct.unpack('<i',blob[4:8])[0]!=4326:bad+=1;continue
  g=shapely.from_wkb(blob[40:]);invalid+=not g.is_valid
  x1,x2,y1,y2=struct.unpack('<4d',blob[8:40]);bad+=any(abs(a-b)>1e-9 for a,b in zip((x1,y1,x2,y2),g.bounds))
 qa[tab]={'count':n,'invalid_geometry_count':invalid,'binary_or_envelope_errors':bad,'declared_type':declared}
assert all(x['invalid_geometry_count']==x['binary_or_envelope_errors']==0 for x in qa.values());db.close();dump('geopackage_validation.json',qa)
stations=csvread('historical_bus_stations_2024.csv');links=csvread('historical_bus_route_stations_2024.csv');routes=csvread('historical_bus_route_quality_2024.csv');cross=csvread('bus_reference_candidates_2024.csv');hosp=csvread('hospital_screening_registry.csv')
stationids={r['StationCode'] for r in stations};refids={r['reference_route_id'] for r in routes};osmids={r['relation_id'] for r in csvread('transit_routes.csv')}
assert len(stationids)==len(stations)==4759
assert len({(r['RouteID'],r['StationCode']) for r in links})==len(links)==9511
assert all(r['StationCode'] in stationids and r['RouteID'] in refids for r in links)
assert all(r['osm_relation_id'] in osmids and r['reference_route_id'] in refids for r in cross)
assert all(r['screen_decision']=='human_hospital_candidate' and r['emergency_tag']=='yes' and r['specialist_scope_flag']=='False' for r in hosp if r['primary_osm_proxy_target']=='True')
readme=f'''# نسخهٔ ۱٫۱ دادهٔ ممیزی‌شده و غنی‌شدهٔ تهران

این نسخه بر دادهٔ ثابت OSM با زمان مبنای 2026-10-29T21:21:26Z بنا شده است. فایل خام PBF، مرز شهر تهران و ۲۲ منطقه و هندسهٔ اصلی معابر تغییر نکرده‌اند. منابع تاریخی و شواهد کمکی جدا و با تاریخ خودشان نگهداری می‌شوند. این بسته برای کار محلی پژوهشی تهیه شده؛ مجوز بازنشر عمومی بخش IranTracking هنوز احراز نشده است.

## تصمیم دربارهٔ پایان کنترل کیفیت

کنترل‌های ساختاری، هندسی، ارجاعی، تطبیق منبع و بررسی محدود وب‌سایت مراکز انجام شده‌اند. تأیید میدانی یا مستقل تک‌تک عوارض شرط بستن این نسخه نیست. نبود شاهد با برچسب «نامعلوم/بررسی‌نشده» باقی می‌ماند؛ آن را درست، غلط یا خدمت تأییدشده تلقی نمی‌کنیم. این نسخه دادهٔ مبنای تحلیل با محدودیت‌های ثبت‌شده است، نه گواه کامل‌بودن سرویس واقعی تهران.

## افزوده‌های عملی

- {s['historical_stations']:,} ایستگاه تاریخی و {s['historical_route_station_links']:,} ارتباط مرتب مسیر–ایستگاه برای {s['historical_route_records']} رکورد مسیر دریافت‌شده از IranTracking، با تاریخ داخلی ۱۴ مهٔ ۲۰۲۴، به CSV و لایه‌های مکانی تبدیل شدند.
- با تفکیک کدهای چندمقداری مثل 101;901، شمار روابط OSM دارای نامزد هم‌کد از ۳۱۵ به {s['crosswalk_relations_with_code_candidate']} رسید؛ {s['direction_status_counts']['ambiguous_direction_candidates_retained']} مورد همچنان جهت مبهم دارند. وجود کد، تأیید مسیر نیست.
- هندسهٔ مرجع و اعضای OSM در هر دو جهت مقایسه شدند. برای {s['both_way_geometry_p95_le_100m']} رابطه، صدک ۹۵ فاصلهٔ نمونه‌ها در هر دو جهت حداکثر ۱۰۰ متر بود؛ آستانه تشخیصی است و کالیبراسیون صحت ندارد. معیار نسخهٔ اول یک‌طرفه و نمونه‌گیری آن متفاوت بود، پس دو عدد مستقیماً مقایسه نشوند.
- {s['historical_stop_osm_route_diagnostic_pairs']:,} ارتباط تشخیصی ایستگاه تاریخی با هندسهٔ رابطهٔ OSM ثبت شد. اینها اتصال مجاز سوار/پیاده‌شدن یا وابستگی دقیق به یال خیابان نیستند.
- هر ۳۲۱ عارضهٔ بیمارستانی حفظ شد. {s['hospital_screen_counts']['excluded_nonhuman']} مورد با برچسب یا نام صریح غیرانسانی از نامزدهای انسانی کنار گذاشته و {s['hospital_screen_counts']['facility_type_needs_review']} مورد به علت نام/برچسب متعارض برای بررسی نگه داشته شدند. حذف از زیرمجموعهٔ تحلیل، حذف از دادهٔ خام نیست.
- زیرمجموعهٔ پیش‌فرض پژوهشی، {s['primary_proxy_target_features']} عارضه در {s['primary_proxy_target_candidate_groups']} گروه مکانی پیشنهادی دارد: نامزد بیمارستان انسانی، emergency=yes و بدون پرچم تخصصیِ شناسایی‌شده. این تعداد، تعداد مراکز مستقل و تأییدشدهٔ اورژانس نیست.

## فایل‌هایی که باید استفاده شوند

| فایل | نقش |
|---|---|
| tehran_context.osm.pbf | دادهٔ خام OSM، بدون تغییر نسبت به نسخهٔ اول |
| tehran_audited_layers.gpkg | لایه‌های نسخهٔ اول به‌علاوهٔ ایستگاه‌های تاریخی، مسیر–ایستگاه مرتب و غربالگری مراکز |
| historical_bus_stations_2024.csv | مختصات و نام ایستگاه‌ها با شناسهٔ منبع |
| historical_bus_route_stations_2024.csv | ترتیب ایستگاه‌ها؛ ترتیب خام منبع حفظ شده است |
| historical_bus_route_quality_2024.csv | پرچم‌های ترتیب، فاصله و ابهام تصویرکردن ایستگاه روی شکل مسیر |
| bus_reference_candidates_2024.csv | همهٔ نامزدهای جهت؛ منبع بررسی اختلاف‌ها |
| bus_reference_crosswalk_2024.csv | یک نامزد تشخیصی منتخب با وضعیت جهت؛ در موارد مبهم، انتخاب به معنی تأیید نیست |
| historical_stop_to_osm_route_diagnostics.csv | فاصلهٔ ایستگاه‌های مرجع تا هندسهٔ اعضای OSM؛ فاقد اتصال مسیریابی تأییدشده |
| hospital_screening_registry.csv | مرجع جدید غربالگری و انتخاب سناریوی مراکز درمانی |
| hospital_external_evidence.json | شواهد محدود از صفحات خود بیمارستان‌ها و موارد ناموفق |
| transit_routes.csv / transit_paths.csv | وضعیت و توالی مشتق‌شدهٔ OSM، همان نسخهٔ اول؛ پرچم‌ها همچنان لازم‌اند |
| baseline_audit | گزارش و شناسنامهٔ نسخهٔ اول برای ردیابی تغییرات |
| enrichment_summary.json / manifest.json | شمارش‌های نسخهٔ جدید، دامنهٔ ادعا و هش فایل‌ها |

فایل bus_reference_comparison_2024.csv، مقایسهٔ قبلی نسخهٔ اول است. برای تطبیق جدید از دو فایل candidates و crosswalk استفاده کنید. raw hospital_candidates نیز فهرست قبل از غربالگری انسانی است؛ هدف‌های تحلیل از registry جدید انتخاب شوند.

## کاربرد علمی مجاز در این مطالعه

دسترسی ساختاری بالقوهٔ ساختمان‌های ثبت‌شدهٔ داخل شهر به نامزدهای بیمارستانی بررسی می‌شود. «سهم ساختمان‌ها» سهم جمعیت نیست. شبکه و بیمارستان بیرون مرز به عنوان زمینه مجازند و سناریوی فقط مراکز داخل شهر جدا مقایسه می‌شود. مرز OSM و قاعدهٔ اکثریت مساحت ساختمان حفظ شده‌اند و معادل‌بودن حقوقی مرز با محدودهٔ مصوب ادعا نمی‌شود.

دادهٔ تاریخی اتوبوس می‌تواند لایهٔ جداگانه یا سناریوی تاریخی باشد. هنوز شکل تمام مسیرهای ۲۰۲۴ به توالی کامل یال‌های خیابانی ۲۰۲۶ نگاشت نشده؛ بنابراین برای مدل خرابی خیابان، همهٔ ۴۷۴ رکورد را به عنوان مسیر دارای وابستگی تأییدشده به خیابان استفاده نکنید. زیرمجموعهٔ OSM غربال‌شده برای آزمون اولیه موجود است و نتیجهٔ آن به کل ناوگان تعمیم داده نمی‌شود.

زمان انتظار، انتقال، سرعت واقعی سرویس، دقت ETA، ظرفیت بیمارستان و ورودی بدون مانع تأیید نشده‌اند. گراف جهت‌دار با اجرای تمام محدودیت‌های گردش مرحلهٔ بعدِ مدل‌سازی است؛ این غنی‌سازی آن را پیاده نکرده است. جایگزینی آن با گراف ساده و گزارش «همهٔ محدودیت‌ها رعایت شد» مجاز نیست.

## سناریوی مراکز درمانی

primary_osm_proxy_target=True زیرمجموعهٔ پیش‌فرضِ مبتنی بر برچسب است. extended_scope_osm_proxy_target=True نامزدهای تخصصی دارای emergency=yes را هم می‌پذیرد. uncertain_hospital_sensitivity_candidate=True برای بررسی حساسیت به برچسب اورژانس نامعلوم است، نه اثبات ارائهٔ اورژانس. موارد facility_type_needs_review و excluded_nonhuman خودکار به سناریوی اصلی وارد نمی‌شوند. گروه‌بندی مکانی صرفاً پیشنهاد رفع شمارش مضاعف است؛ شناسهٔ قطعی بیمارستان نیست.

غربالگری نام‌ها محافظه‌کارانه و واژه‌محور است و احتمال خطای مثبت و منفی دارد؛ به عنوان طبقه‌بندی بالینی معرفی نشود. شواهد سایت عرفان و آرمان فقط وجود بخش معرفی‌شده را پشتیبانی می‌کنند؛ فعالیت لحظه‌ای، پذیرش همگانی، هزینه، ظرفیت و ورودی دقیق را ثابت نمی‌کنند. صفحهٔ آرمان تاریخ ۲۰۲۲ دارد. برچسب «فاقد شاهد» به معنی نبود خدمت نیست.

## نصب اپ لازم نیست

فایل مرجع مستقلاً دریافت شده است. بازبینی مستقیم نشان داد تاریخ Updated at پایین وبلاگ از site.time، یعنی زمان ساخت کل سایت، می‌آید. دانلود تازهٔ پایگاه اتوبوس با هش قبلی یکسان و تاریخ داخلی آن همچنان ۲۰۲۴ است. سرویس فهرست مترو خالی بود، ولی سه شناسهٔ منتشرشده پاسخ ایستگاهی دادند. خالی‌بودن فهرست به معنی بی‌داده‌بودن همهٔ API مترو نیست. دریافت اطلاعات خصوصی، پیامک یا نصب نسخهٔ ناسازگار شرط ادامهٔ کار نیست.

## مجوز و منابع

OSM: © OpenStreetMap contributors، ODbL. منبع اصلی Geofabrik Iran است. فایل historical SQLite در sources قرار دارد؛ دسترسی عمومی به آن، مجوز بازنشر عمومی را به‌تنهایی ثابت نمی‌کند. هیچ داده‌ای از API نشان، بلد یا گوگل به این بسته افزوده نشده و هیچ درخواست پولی انجام نشده است.
'''
(R/'README_fa.md').write_text(readme,encoding='utf8')
methods='''# متن پیشنهادی گزارش داده و محدودیت‌ها

محدودهٔ تقاضای مطالعه با مرز شهر تهران در OSM و ۲۲ منطقهٔ آن تعریف شد. یک عکس ثابت از دادهٔ OSM دریافت و ارجاع‌ها، اعتبار هندسه، جهت و پیوستگی مسیرها، محدودیت‌های گردش و موارد نامطمئن ثبت شدند. برای ساختمان‌ها قاعدهٔ اکثریت مساحت داخل مرز اعمال شد؛ شبکه و مراکز بیرون مرز به عنوان زمینه حفظ شدند. یک پایگاه عمومی مسیر و ایستگاه اتوبوس با تاریخ داخلی مهٔ ۲۰۲۴ جداگانه دریافت شد. مقایسهٔ کد، نام مبدأ–مقصد، نزدیکی هندسه در هر دو جهت و فاصلهٔ ایستگاه‌ها برای شناسایی توافق و اختلاف منابع انجام شد. دادهٔ تاریخی به عنوان واقعیت عملیاتی سال ۲۰۲۶ معرفی نشد.

نامزدهای مراکز اورژانس از عوارض دارای برچسب بیمارستان استخراج و موارد غیرانسانی یا دارای نام/برچسب متعارض از زیرمجموعهٔ اصلی جدا شدند. وجود بخش اورژانس برای نمونهٔ محدودی از مراکز از وب‌سایت خود آنها بررسی شد؛ این نمونه، تصادفی یا نمایندهٔ همهٔ مراکز نبود. برای بقیه، نبود تأیید مستقل صریحاً ثبت شد. دادهٔ خام حفظ و انتخاب مراکز بر اساس سناریو گزارش شد.

با وجود این کنترل‌ها، کامل‌بودن پوشش OSM، فعالیت جاری همهٔ خطوط، تمام ایستگاه‌های مجاز سوار/پیاده‌شدن، صحت بالینی همهٔ مقاصد، ورودی‌ها و عبور بدون مانع تضمین نشده است. مطالعه بر ساختار ثبت‌شده و دسترسی بالقوه مبتنی است؛ دسترسی محاسبه‌شده، زمان واقعی پاسخ آمبولانس یا سهم جمعیت نیست. توقف گردآوری در این نسخه به معنی حل‌شدن همهٔ موارد نامطمئن نیست؛ به معنی ثابت‌کردن دادهٔ موجود همراه با استثناهای قابل ردیابی است.

آستانه‌های ۱۰۰ متر فاصله و اختلاف شباهت نام ۰٫۱، قواعد تشخیصی و ثبت‌شده‌اند، نه آستانه‌های کالیبره‌شدهٔ صحت. پرچم عقب‌گرد تصویرکردن ایستگاه روی شکل مسیر ممکن است ناشی از حلقه یا رفت‌وبرگشت باشد و به‌تنهایی خطای منبع را اثبات نمی‌کند. خطاهای دسته‌بندی واژه‌محور مراکز و پوشش ناقص منابع باید در تحلیل حساسیت لحاظ شوند.
'''
(R/'METHODS_AND_LIMITATIONS_fa.md').write_text(methods,encoding='utf8')
(R/'CHANGELOG_fa.md').write_text('''# تغییرات نسخهٔ ۱٫۱ نسبت به ۱٫۰

- افزوده‌شدن جدول و لایهٔ ایستگاه‌های تاریخی و ترتیب مسیر–ایستگاه.
- اصلاح تطبیق ref چندمقداری و ثبت همهٔ نامزدهای جهت.
- افزوده‌شدن مقایسهٔ هندسی دوطرفه و تشخیص فاصلهٔ ایستگاه از مسیر.
- افزوده‌شدن غربالگری انسانی مراکز و شواهد محدود از وب‌سایت مراکز.
- ثبت نتیجهٔ بازبینی تاریخ وبلاگ، دانلود دوبارهٔ مرجع و آزمون سه ایستگاه مترو.
- حفظ فایل خام، مرز، راه‌ها و وضعیت غربالگری مسیرهای OSM نسخهٔ اول.
- هیچ شکاف مسیر با خیابان حدسی پر نشده، سرویس فعال گواهی نشده و گراف مسیریابی کامل ساخته نشده است.
''',encoding='utf8')
combined=json.loads((B/'final_audit_summary.json').read_text(encoding='utf8'));combined['version']='1.1';combined['enrichment']=s;combined['geopackage_verification']=qa;combined['current_release_status']='frozen source-based research dataset with historical station enrichment and documented unresolved uncertainties';dump('final_audit_summary.json',combined)
(R/'scripts').mkdir(exist_ok=True);shutil.copy2('work/enrich_v11.py',R/'scripts/enrich_v11.py');shutil.copy2('work/finalize_v11.py',R/'scripts/finalize_v11.py')
# Compact, read-only verification notebook, executed cell-by-cell and saved with outputs.
cells=[nbformat.v4.new_markdown_cell('# Verify Tehran dataset v1.1\nRead-only release verification. Source-based quality flags are preserved; no real-world certification is inferred.')]
code1="""import pathlib,json,csv,hashlib,sqlite3
R=pathlib.Path.cwd()
if not (R/'enrichment_summary.json').exists():
    R=R/'outputs/tehran_dataset_v1_1'
summary=json.loads((R/'enrichment_summary.json').read_text(encoding='utf8'))
print({k:summary[k] for k in ['version','historical_route_records','historical_stations','historical_route_station_links','crosswalk_relations_with_code_candidate','primary_proxy_target_features']})
"""
code2="""def readcsv(name):
    return list(csv.DictReader(open(R/name,encoding='utf-8-sig')))
stations=readcsv('historical_bus_stations_2024.csv')
links=readcsv('historical_bus_route_stations_2024.csv')
routes=readcsv('historical_bus_route_quality_2024.csv')
sid={r['StationCode'] for r in stations};rid={r['reference_route_id'] for r in routes}
assert len(sid)==len(stations)==4759
assert len({(r['RouteID'],r['StationCode']) for r in links})==len(links)==9511
assert all(r['StationCode'] in sid and r['RouteID'] in rid for r in links)
print('Historical station keys and route-station references: pass')
print('Routes with diagnostic flags:',sum(bool(r['flags']) for r in routes))
"""
code3="""manifest=json.loads((R/'manifest.json').read_text(encoding='utf8'))
for name,metadata in manifest['files'].items():
    assert hashlib.sha256((R/name).read_bytes()).hexdigest()==metadata['sha256'],name
db=sqlite3.connect('file:'+str(R/'tehran_audited_layers.gpkg')+'?mode=ro',uri=True)
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
print('Manifest hashes: pass; GeoPackage integrity: pass')
print('Layers:',len(db.execute('SELECT table_name FROM gpkg_contents').fetchall()))
db.close()
"""
for code in [code1,code2,code3]:cells.append(nbformat.v4.new_code_cell(code))
nb=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}});nbformat.validate(nb)
nbformat.write(nb,R/'verify_release.ipynb')
# Manifest deliberately excludes itself and the verifier notebook to avoid a circular hash.
manifest={**parent,'dataset_id':'tehran-osm-20261029T212126Z-v1.1','version':'1.1','parent_dataset_id':parent['dataset_id'],'release_status':'frozen_with_documented_limitations','frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'enrichment_summary':s,'files':{},'manifest_exclusions':['manifest.json','verify_release.ipynb'],'notebook_execution':'sequential Python cell execution with saved outputs; nbformat validated'}
manifest['readiness']={**parent['readiness'],'historical_station_and_order_tables':True,'historical_bus_paths_have_certified_current_street_dependencies':False,'human_hospital_screening_registry':True,'limited_hospital_website_evidence':True}
for p in sorted(R.rglob('*')):
 if p.is_file() and p.relative_to(R).as_posix() not in manifest['manifest_exclusions']:
  manifest['files'][p.relative_to(R).as_posix()]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
dump('manifest.json',manifest)
ns={};nb.cells[1].source="R_override="+repr(str(R.resolve()))+"\n"+nb.cells[1].source.replace('R=pathlib.Path.cwd()','R=pathlib.Path(R_override)')
# The delivered notebook remains portable; override exists only in the execution copy.
portable=nb.cells[1].source;ns={}
for i,cell in enumerate(nb.cells[1:],1):
 buf=io.StringIO()
 with contextlib.redirect_stdout(buf):exec(cell.source,ns)
 cell.execution_count=i;cell.outputs=[nbformat.v4.new_output('stream',name='stdout',text=buf.getvalue())]
nb.cells[1].source=code1;nbformat.validate(nb);nbformat.write(nb,R/'verify_release.ipynb')
z=pathlib.Path('outputs/tehran_dataset_v1.1.zip')
with zipfile.ZipFile(z,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
 for p in sorted(R.rglob('*')):
  if p.is_file():archive.write(p,'tehran_dataset_v1_1/'+p.relative_to(R).as_posix())
receipt={'file':z.name,'bytes':z.stat().st_size,'sha256':hashlib.sha256(z.read_bytes()).hexdigest(),'dataset_id':manifest['dataset_id'],'base_pbf_unchanged':True,'geometry_layers_validated':len(qa),'independent_service_certification_required_to_freeze':False}
pathlib.Path('outputs/tehran_dataset_v1.1_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps(receipt,indent=2))

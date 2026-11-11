RailPlanner V3 — תחנות עם השלמה אוטומטית ושליפת שעות אוטומטית כאשר schedule.json קיים.

העלה את כל הקבצים כולל תיקיית .github למאגר GitHub חדש.
ב-GitHub: Settings > Pages > Deploy from branch > main / root.
ב-Actions: הרץ Update Israel Railways timetable באמצעות Run workflow.
בדוק שהקובץ schedule.json נוצר בשורש המאגר, ושהאתר מציג שעות.
אם אין קובץ או שהעדכון נכשל, לא יוצגו שעות אוטומטיות; אפשר להזין ידנית.
שעות מקור ציבורי אינן תחליף למערכת התפעולית.
הסקריפט עדיין לא נבדק מקצה לקצה מול נתוני GTFS חיים.

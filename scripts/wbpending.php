<?php

switch ($_GET['mode']) {
  case 'pending':
    $query = "select taluka, village, concat('https://maps.google.com?q=', latitude, ',', longitude, '&t=h') as GMap
from wrd . water_bodies
where wb_type <> 'Spring'
and census_id is NULL
order by taluka, village";
    break;
  case 'enumerated':
    $query = "select taluka, village,
       count(census_id) as enumerated,
       sum(case when census_id is NULL then 1 else 0 end) as pending,
       count(wb_id) as total
from wrd . water_bodies w
where w . wb_type <> 'Spring'
group by taluka, village
order by taluka, village";
    break;
  case 'distance':
    $query = "select wb.wb_id, cs.unique_id, round(ST_distance(wb.geom, ST_Transform(cs.geom, 7779))) as distance
from wrd.\"combined_waterBodySchedule\" cs
join wrd.water_bodies wb
on cs.unique_id = wb.census_id
order by distance desc";
    break;

}
$db = pg_connect("dbname='wrd' host=db-postgresql-blr1-49618-do-user-1003361-0.db.ondigitalocean.com port=25060 user='wrd' password='npsdyptxa7rh02vr' sslmode=require");

$result = pg_query($db, $query);

header('Content-Type: text/csv');

$output = fopen('php://output', 'w');

if ($result && pg_num_rows($result) > 0) {
    // Print column headers
    $firstRow = pg_fetch_assoc($result, 0);
    fputcsv($output, array_keys($firstRow));
    
    // Reset result pointer and print rows
    pg_result_seek($result, 0);
    while ($row = pg_fetch_assoc($result)) {
        fputcsv($output, $row);
    }
}

fclose($output);
pg_close($db);

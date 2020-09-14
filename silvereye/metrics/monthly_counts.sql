-- Upsert publisher metric counts to silvereye_publishermonthlycounts
WITH daily_sum as (
    select pub.id,
--     pub.publisher_name,
           DATE_TRUNC('month',TO_DATE(release_json ->> 'date', 'YYYY-MM-DD'))                          as date,
           SUM(CASE WHEN release_json -> 'tag' ->> 0 = 'tender' THEN 1 ELSE 0 END) as count_tenders,
           SUM(CASE WHEN release_json -> 'tag' ->> 0 = 'award' THEN 1 ELSE 0 END)  as count_awards,
           SUM(CASE WHEN release_json -> 'tag' ->> 0 = 'implementation' THEN 1 ELSE 0 END)  as count_spend
    from bluetail_ocds_release_json_view rel
             LEFT JOIN bluetail_ocds_package_data_view pac ON (rel.package_data_id = pac.id)
             LEFT JOIN input_supplieddata sup on (pac.supplied_data_id = sup.id)
             INNER JOIN silvereye_filesubmission sf on sup.id = sf.supplied_data_id
             LEFT JOIN silvereye_publisher_metadata pub on sf.publisher_id = pub.id
    where rel.package_data_id notnull
    group by pub.id,
             DATE_TRUNC('month', TO_DATE(release_json ->> 'date', 'YYYY-MM-DD'))
    order by date
)
INSERT
INTO silvereye_publishermonthlycounts
(date,
 count_tenders,
 count_awards,
 count_spend,
 publisher_id)
SELECT date,
       count_tenders,
       count_awards,
       count_spend,
       id
FROM daily_sum
ON CONFLICT (publisher_id, date)
DO UPDATE SET
        count_tenders=excluded.count_tenders,
        count_awards=excluded.count_awards,
        count_spend=excluded.count_spend
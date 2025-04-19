SELECT s.id as store_id, s.name as store_name, m.id as item_id, m.name as item_name, sli.store_id
FROM shopping_list_item sli
JOIN master_item m ON sli.item_id = m.id
LEFT JOIN store s ON sli.store_id = s.id
WHERE m.name = 'Milk';

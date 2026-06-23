# #INDEX ANALYSIS 
MATCHUP_BRACKETA INDEX

### Explain Analysis 1

mysql> EXPLAIN ANALYZE SELECT *FROM Matchups WHERE bracket_id=12 AND round=1;
+------------------------------------------------------------------------------------------------------------------------------------------------+
| EXPLAIN                                                                                                                                        |
+------------------------------------------------------------------------------------------------------------------------------------------------+
| -> Index lookup on Matchups using uq_matchups_slot (bracket_id = 12, round = 1)  (cost=0.35 rows=1) (actual time=0.201..0.201 rows=0 loops=1)
 |
+------------------------------------------------------------------------------------------------------------------------------------------------+
1 row in set (0.003 sec)

### Analysis 
Explain analysis shows the mysql is using uq_matchup_slot index to find the rows matching
bracket_id=12 and round=1. There is low cost estimation meaning it is optimal. row=0 because 
there is none of this data in the database.Overall, the uq_matchups_slot index for 'bracket_id and round allows mysql to locate the matchup without going through the entire table and makes
looking up faster.


### Explain analysis 2

mysql> EXPLAIN ANALYZE SELECT *FROM Predictions WHERE user_id=1;
+----------------------------------------------------------------------------------------------------------------------------+
| EXPLAIN                                                                                                                    |
+----------------------------------------------------------------------------------------------------------------------------+
| -> Index lookup on Predictions using user_id (user_id = 1)  (cost=1.3 rows=8) (actual time=0.0621..0.0671 rows=8 loops=1)
 |
+----------------------------------------------------------------------------------------------------------------------------+
1 row in set (0.001 sec)

mysql> 

## Analysis

Explain analysis shows that mysql is using user_id and index to find rows that will matchup user_id=1. There is low cost estimate of 1.3 and time of execution is  0.06. There are 8 rows, meaning that this is locating the predictions. user_id index allows us to quickly lookup matching rows without going through the entire table. Being able to locate predictions quickly makes the query fast. 
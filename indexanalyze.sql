EXPLAIN ANALYZE SELECT *FROM Matchups WHERE bracket_id=12 AND round=1;
CREATE INDEX  matchup_bracketa ON Matchups(bracket_id,round);
EXPLAIN ANALYZE SELECT *FROM Matchups WHERE bracket_id=12 AND round=1;

EXPLAIN ANALYZE SELECT *FROM Predictions WHERE user_id=1;
CREATE INDEX  prediction_user ON Predictions(user_id);
EXPLAIN ANALYZE SELECT *FROM Predictions WHERE user_id=435;
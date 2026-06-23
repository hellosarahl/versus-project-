-- VERSUS skeleton schema
-- Run:  mysql -u root -p versus < schema.sql
--
-- The four core tables for Phase I.
-- Students will extend with: predictions, votes, achievements,
-- user_achievements, follows, comments, plus triggers and a stored procedure.

DROP DATABASE IF EXISTS versus;
CREATE DATABASE versus;
USE versus;

CREATE TABLE Users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password      VARCHAR(255) NOT NULL,
    bio           TEXT,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Brackets (
    bracket_id           INT AUTO_INCREMENT PRIMARY KEY,
    host_id              INT NOT NULL,
    title                VARCHAR(255) NOT NULL,
    description          TEXT,
    entrant_count        INT NOT NULL,
    status               ENUM(
                             'draft',
                             'predictions_open',
                             'round_1','round_2','round_3','round_4','round_5',
                             'completed'
                         ) NOT NULL DEFAULT 'predictions_open',
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_entrant_count CHECK (entrant_count IN (4,8,16,32)),
    CONSTRAINT fk_brackets_host  FOREIGN KEY (host_id) REFERENCES Users(user_id)
);

CREATE TABLE Entrants (
    entrant_id   INT AUTO_INCREMENT PRIMARY KEY,
    bracket_id   INT NOT NULL,
    seed         INT NOT NULL,
    name         VARCHAR(255) NOT NULL,
    CONSTRAINT fk_entrants_bracket FOREIGN KEY (bracket_id) REFERENCES Brackets(bracket_id),
    CONSTRAINT uq_entrants_seed    UNIQUE (bracket_id, seed)
);

CREATE TABLE Matchups (
    matchup_id          INT AUTO_INCREMENT PRIMARY KEY,
    bracket_id          INT NOT NULL,
    round               INT NOT NULL,
    slot                INT NOT NULL,
    entrant_a_id        INT,
    entrant_b_id        INT,
    winner_entrant_id   INT,
    votes_a             INT NOT NULL DEFAULT 0,
    votes_b             INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_matchups_bracket FOREIGN KEY (bracket_id)        REFERENCES Brackets(bracket_id),
    CONSTRAINT fk_matchups_a       FOREIGN KEY (entrant_a_id)      REFERENCES Entrants(entrant_id),
    CONSTRAINT fk_matchups_b       FOREIGN KEY (entrant_b_id)      REFERENCES Entrants(entrant_id),
    CONSTRAINT fk_matchups_winner  FOREIGN KEY (winner_entrant_id) REFERENCES Entrants(entrant_id),
    CONSTRAINT uq_matchups_slot    UNIQUE (bracket_id, round, slot)
);


CREATE TABLE Predictions(
     prediction_id INT PRIMARY KEY AUTO_INCREMENT,
     user_id INT, 
    correct BOOLEAN,
    matchup_id INT,
    points_earned INT,
    entrant_id INT,
     submitted_at DATETIME,
     UNIQUE(user_id,matchup_id),
     FOREIGN KEY(matchup_id)REFERENCES Matchups(matchup_id),
    FOREIGN KEY(user_id) REFERENCES Users(user_id),
     FOREIGN KEY(entrant_id) REFERENCES Entrants(entrant_id)
     );

DELIMITER //
CREATE TRIGGER before_predict
BEFORE INSERT ON Predictions
FOR EACH ROW
BEGIN 
DECLARE bracket_status VARCHAR(20);
DECLARE matchup_round INT;
SELECT b.status, m.round
INTO bracket_status,matchup_round
FROM Matchups m
JOIN Brackets b ON m.bracket_id=b.bracket_id 
WHERE m.matchup_id=NEW.matchup_id;
IF bracket_status <>'predictions_open'
THEN 
SIGNAL SQLSTATE '45000'
SET MESSAGE_TEXT='prediction can be submitted when prediction is open';
END IF;
IF matchup_round<>1 THEN
SIGNAL SQLSTATE '45000'
SET MESSAGE_TEXT='prediction can be submitted for round 1';
END IF;
END //
DELIMITER ;

CREATE TABLE Votes(
    vote_id INT AUTO_INCREMENT PRIMARY KEY, 
    user_id INT NOT NULL,
    matchup_id INT NOT NULL,
    voted_for INT NOT NULL,
 
  
    voted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(matchup_id)REFERENCES Matchups(matchup_id),
     FOREIGN KEY(user_id) REFERENCES Users(user_id),
      FOREIGN KEY(voted_for) REFERENCES Entrants(entrant_id),
      UNIQUE(user_id, matchup_id));


DELIMITER //
CREATE TRIGGER vote_check
BEFORE INSERT ON Votes
FOR EACH ROW
BEGIN 

DECLARE rm INT;
DECLARE se VARCHAR(50);
SELECT m.round, b.status 
INTO rm, se
FROM Matchups m
JOIN Brackets b on m.bracket_id=b.bracket_id
WHERE m.matchup_id=NEW.matchup_id;
IF se!=CONCAT('round_',rm) THEN
SIGNAL SQLSTATE '45000'
SET MESSAGE_TEXT='vote not open';
END IF;
END //
DELIMITER ;


DELIMITER //

CREATE PROCEDURE close_round(IN bid INT, IN r INT)
BEGIN 

START TRANSACTION;

UPDATE Matchups
SET winner_entrant_id= 
CASE WHEN votes_a>=votes_b THEN entrant_a_id
ELSE entrant_b_id
END 
WHERE bracket_id=bid AND round=r;

UPDATE Predictions p 
JOIN Matchups m on p.matchup_id=m.matchup_id
SET
p.correct=(p.entrant_id= m.winner_entrant_id), 
p.points_earned=IF(p.entrant_id=m.winner_entrant_id, 1,0)
WHERE m.bracket_id=bid AND m.round=r;

UPDATE Matchups m1 
JOIN Matchups m2
ON m1.bracket_id=m2.bracket_id 
AND m2.round=r+1
AND m2.slot=FLOOR((m1.slot+1)/2)
SET m2.entrant_a_id=m1.winner_entrant_id
WHERE m1.bracket_id=bid AND m1.round=r AND m1.slot%2=1;

UPDATE Matchups m1 
JOIN Matchups m2
ON m1.bracket_id=m2.bracket_id 
AND m2.round=r+1
AND m2.slot=FLOOR((m1.slot+1)/2)
SET m2.entrant_b_id=m1.winner_entrant_id
WHERE m1.bracket_id=bid AND m1.round=r AND m1.slot%2=0;


UPDATE Brackets 
SET status=IF(r=CASE entrant_count WHEN 4 THEN 2 WHEN 8 THEN 3 WHEN 16 THEN 4 WHEN 32 THEN 5 END,
'completed',CONCAT('round_',r+1))
WHERE bracket_id=bid; 
COMMIT; 
END //
DELIMITER ;

CREATE TABLE Achievements(
    achievement_code VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    name VARCHAR(100) NOT NULL);

CREATE TABLE User_Achievements(
     user_id INT NOT NULL,
    achievement_code VARCHAR(50) NOT NULL,
   
    earned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id,achievement_code),
    FOREIGN KEY(achievement_code) REFERENCES Achievements(achievement_code),
    FOREIGN KEY(user_id) REFERENCES Users(user_id));

INSERT INTO Achievements VALUES
('bracket_maker','Bracket Maker','Created first bracket'),('locked_in','Locked In','Submitted prediction'),


DELIMITER //
CREATE TRIGGER bracket_maker_trigger
AFTER INSERT ON Brackets
FOR EACH ROW 
BEGIN 
DECLARE i INT;
SELECT COUNT(*)
INTO i 
FROM Brackets
WHERE host_id=NEW.host_id;
IF i=1 THEN 
INSERT IGNORE INTO User_Achievements(user_id, achievement_code)
VALUES(NEW.host_id,'bracket_maker');
END IF;
END //
DELIMITER ;

DELIMITER //
CREATE TRIGGER locked_trigger
AFTER INSERT ON Predictions
FOR EACH ROW 
BEGIN 
DECLARE i INT;
SELECT COUNT(*)
INTO i 
FROM Predictions
WHERE user_id=NEW.user_id;
IF i=10 THEN 
INSERT IGNORE INTO User_Achievements(user_id, achievement_code)
VALUES(NEW.user_id,'locked_in');
END IF;
END //
DELIMITER ;



CREATE TABLE Follows(
    follower_id INT NOT NULL,
    followed_id INT NOT NULL,
    followed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, followed_id),
    FOREIGN KEY(followed_id)REFERENCES Users(user_id),
    FOREIGN KEY(follower_id)REFERENCES Users(user_id),
    
    CHECK (follower_id<>followed_id));


CREATE TABLE Comments(
    comment_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    content TEXT NOT NULL,
    matchup_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (matchup_id) REFERENCES Matchups(matchup_id));


CREATE INDEX  matchup_bracketa ON Matchups(bracket_id,round);
CREATE INDEX  prediction_user ON Predictions(user_id);
CREATE INDEX vote_match ON Votes (matchup_id);
CREATE INDEX follows_followed ON Follows(followed_id);










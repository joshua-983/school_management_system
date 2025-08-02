-- MySQL dump 10.13  Distrib 8.0.42, for Linux (x86_64)
--
-- Host: localhost    Database: school_db
-- ------------------------------------------------------
-- Server version	8.0.42-0ubuntu0.24.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `accounts_customuser`
--

DROP TABLE IF EXISTS `accounts_customuser`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_customuser` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  `phone_number` varchar(20) NOT NULL,
  `address` longtext NOT NULL,
  `date_of_birth` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_customuser`
--

LOCK TABLES `accounts_customuser` WRITE;
/*!40000 ALTER TABLE `accounts_customuser` DISABLE KEYS */;
INSERT INTO `accounts_customuser` VALUES (12,'pbkdf2_sha256$600000$0VFQ4kdC7wAu7oSFX1OsvB$m8ONEOk7LUyZkbwzpdoHlAMIlLNapKUoBjqyRzDfMbo=','2025-07-02 14:10:42.071222',1,'Admin_Sch','','','admin@gmail.com',1,1,'2025-06-09 16:00:27.000000','','',NULL),(13,'pbkdf2_sha256$600000$geE8j1kuvjwP13PIr09OsY$JCshkwoOR3vILEBiOK2ta3VkrnrbFwRu4aXtv0gObWM=',NULL,0,'STU-001','Kofi','Abraham','',0,1,'2025-06-09 16:12:39.478344','','',NULL),(14,'pbkdf2_sha256$600000$nWFP9URNVGPX8n2ykMzUwg$qAURQTidVyIlA+lyFI4eaHl4NetqoPoRmGYfBXx1PjM=','2025-07-02 14:07:25.975370',0,'clement_esh','Clement','Eshun','clement@gmail.com',1,1,'2025-06-09 16:20:24.000000','002544444444','DUNKWA-ATECHEM','2008-07-01'),(15,'pbkdf2_sha256$600000$ALQqXm6uymJnfBzT8IatAa$O3Qi9BFkoOUa2ZiRPLMZ/eSafaR/5lzdM/zZbzI/HK8=',NULL,0,'STU-002','Yaw','Abraham','',0,1,'2025-06-11 15:51:58.183555','','',NULL),(16,'pbkdf2_sha256$600000$rklyXuT5M4OEsWrz7qUxGL$+vi14bK2O8Yo5lTaaB8bt2Ep6FF2pavPE4aLifml8hI=',NULL,0,'teacher_mensah@gmail.com','Solomon','Adjei','',1,1,'2025-06-18 11:32:25.775425','','',NULL),(17,'pbkdf2_sha256$600000$ZiUZL88rybMtPWKITSBFCg$hJQfD7+aUMSj3bX4NzDZndaYLKJcvpnLqMNCmZVKbEk=',NULL,0,'STU-004','John','Mensah','',0,1,'2025-06-21 15:26:56.177932','','',NULL),(18,'pbkdf2_sha256$600000$BRwR5mBwM4DN3EQIOYj1M4$c8z8+668zot8jOYsuLGtn9aP3vQXhIsHEpaX0yqm/Qs=',NULL,0,'teststudent1','Test','Student','',0,1,'2025-06-30 23:55:10.004381','','',NULL);
/*!40000 ALTER TABLE `accounts_customuser` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_customuser_groups`
--

DROP TABLE IF EXISTS `accounts_customuser_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_customuser_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `customuser_id` bigint NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `accounts_customuser_groups_customuser_id_group_id_c074bdcb_uniq` (`customuser_id`,`group_id`),
  KEY `accounts_customuser_groups_group_id_86ba5f9e_fk_auth_group_id` (`group_id`),
  CONSTRAINT `accounts_customuser__customuser_id_bc55088e_fk_accounts_` FOREIGN KEY (`customuser_id`) REFERENCES `accounts_customuser` (`id`),
  CONSTRAINT `accounts_customuser_groups_group_id_86ba5f9e_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_customuser_groups`
--

LOCK TABLES `accounts_customuser_groups` WRITE;
/*!40000 ALTER TABLE `accounts_customuser_groups` DISABLE KEYS */;
INSERT INTO `accounts_customuser_groups` VALUES (5,14,1),(6,14,2);
/*!40000 ALTER TABLE `accounts_customuser_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_customuser_user_permissions`
--

DROP TABLE IF EXISTS `accounts_customuser_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_customuser_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `customuser_id` bigint NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `accounts_customuser_user_customuser_id_permission_9632a709_uniq` (`customuser_id`,`permission_id`),
  KEY `accounts_customuser__permission_id_aea3d0e5_fk_auth_perm` (`permission_id`),
  CONSTRAINT `accounts_customuser__customuser_id_0deaefae_fk_accounts_` FOREIGN KEY (`customuser_id`) REFERENCES `accounts_customuser` (`id`),
  CONSTRAINT `accounts_customuser__permission_id_aea3d0e5_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=433 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_customuser_user_permissions`
--

LOCK TABLES `accounts_customuser_user_permissions` WRITE;
/*!40000 ALTER TABLE `accounts_customuser_user_permissions` DISABLE KEYS */;
INSERT INTO `accounts_customuser_user_permissions` VALUES (361,12,1),(362,12,2),(363,12,3),(364,12,4),(365,12,5),(366,12,6),(367,12,7),(368,12,8),(369,12,9),(370,12,10),(371,12,11),(372,12,12),(373,12,13),(374,12,14),(375,12,15),(376,12,16),(377,12,17),(378,12,18),(379,12,19),(380,12,20),(381,12,21),(382,12,22),(383,12,23),(384,12,24),(385,12,25),(386,12,26),(387,12,27),(388,12,28),(389,12,29),(390,12,30),(391,12,31),(392,12,32),(393,12,33),(394,12,34),(395,12,35),(396,12,36),(397,12,37),(398,12,38),(399,12,39),(400,12,40),(401,12,41),(402,12,42),(403,12,43),(404,12,44),(405,12,45),(406,12,46),(407,12,47),(408,12,48),(409,12,49),(410,12,50),(411,12,51),(412,12,52),(413,12,53),(414,12,54),(415,12,55),(416,12,56),(417,12,57),(418,12,58),(419,12,59),(420,12,60),(421,12,61),(422,12,62),(423,12,63),(424,12,64),(425,12,65),(426,12,66),(427,12,67),(428,12,68),(429,12,69),(430,12,70),(431,12,71),(432,12,72),(289,14,1),(290,14,2),(291,14,3),(292,14,4),(293,14,5),(294,14,6),(295,14,7),(296,14,8),(297,14,9),(298,14,10),(299,14,11),(300,14,12),(301,14,13),(302,14,14),(303,14,15),(304,14,16),(305,14,17),(306,14,18),(307,14,19),(308,14,20),(309,14,21),(310,14,22),(311,14,23),(312,14,24),(313,14,25),(314,14,26),(315,14,27),(316,14,28),(317,14,29),(318,14,30),(319,14,31),(320,14,32),(321,14,33),(322,14,34),(323,14,35),(324,14,36),(325,14,37),(326,14,38),(327,14,39),(328,14,40),(329,14,41),(330,14,42),(331,14,43),(332,14,44),(333,14,45),(334,14,46),(335,14,47),(336,14,48),(337,14,49),(338,14,50),(339,14,51),(340,14,52),(341,14,53),(342,14,54),(343,14,55),(344,14,56),(345,14,57),(346,14,58),(347,14,59),(348,14,60),(349,14,61),(350,14,62),(351,14,63),(352,14,64),(353,14,65),(354,14,66),(355,14,67),(356,14,68),(357,14,69),(358,14,70),(359,14,71),(360,14,72);
/*!40000 ALTER TABLE `accounts_customuser_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group`
--

DROP TABLE IF EXISTS `auth_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group`
--

LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
INSERT INTO `auth_group` VALUES (2,'ADMIN'),(1,'clement permissions');
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group_permissions`
--

DROP TABLE IF EXISTS `auth_group_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=145 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group_permissions`
--

LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
INSERT INTO `auth_group_permissions` VALUES (1,1,1),(2,1,2),(3,1,3),(4,1,4),(5,1,5),(6,1,6),(7,1,7),(8,1,8),(9,1,9),(10,1,10),(11,1,11),(12,1,12),(13,1,13),(14,1,14),(15,1,15),(16,1,16),(17,1,17),(18,1,18),(19,1,19),(20,1,20),(21,1,21),(22,1,22),(23,1,23),(24,1,24),(25,1,25),(26,1,26),(27,1,27),(28,1,28),(29,1,29),(30,1,30),(31,1,31),(32,1,32),(33,1,33),(34,1,34),(35,1,35),(36,1,36),(37,1,37),(38,1,38),(39,1,39),(40,1,40),(41,1,41),(42,1,42),(43,1,43),(44,1,44),(45,1,45),(46,1,46),(47,1,47),(48,1,48),(49,1,49),(50,1,50),(51,1,51),(52,1,52),(53,1,53),(54,1,54),(55,1,55),(56,1,56),(57,1,57),(58,1,58),(59,1,59),(60,1,60),(61,1,61),(62,1,62),(63,1,63),(64,1,64),(65,1,65),(66,1,66),(67,1,67),(68,1,68),(70,1,69),(71,1,70),(72,1,71),(69,1,72),(73,2,1),(74,2,2),(75,2,3),(76,2,4),(77,2,5),(78,2,6),(79,2,7),(80,2,8),(81,2,9),(82,2,10),(83,2,11),(84,2,12),(85,2,13),(86,2,14),(87,2,15),(88,2,16),(89,2,17),(90,2,18),(91,2,19),(92,2,20),(93,2,21),(94,2,22),(95,2,23),(96,2,24),(97,2,25),(98,2,26),(99,2,27),(100,2,28),(101,2,29),(102,2,30),(103,2,31),(104,2,32),(105,2,33),(106,2,34),(107,2,35),(108,2,36),(109,2,37),(110,2,38),(111,2,39),(112,2,40),(113,2,41),(114,2,42),(115,2,43),(116,2,44),(117,2,45),(118,2,46),(119,2,47),(120,2,48),(121,2,49),(122,2,50),(123,2,51),(124,2,52),(125,2,53),(126,2,54),(127,2,55),(128,2,56),(129,2,57),(130,2,58),(131,2,59),(132,2,60),(133,2,61),(134,2,62),(135,2,63),(136,2,64),(137,2,65),(138,2,66),(139,2,67),(140,2,68),(141,2,69),(142,2,70),(143,2,71),(144,2,72);
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_permission`
--

DROP TABLE IF EXISTS `auth_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=97 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_permission`
--

LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES (1,'Can add log entry',1,'add_logentry'),(2,'Can change log entry',1,'change_logentry'),(3,'Can delete log entry',1,'delete_logentry'),(4,'Can view log entry',1,'view_logentry'),(5,'Can add permission',2,'add_permission'),(6,'Can change permission',2,'change_permission'),(7,'Can delete permission',2,'delete_permission'),(8,'Can view permission',2,'view_permission'),(9,'Can add group',3,'add_group'),(10,'Can change group',3,'change_group'),(11,'Can delete group',3,'delete_group'),(12,'Can view group',3,'view_group'),(13,'Can add content type',4,'add_contenttype'),(14,'Can change content type',4,'change_contenttype'),(15,'Can delete content type',4,'delete_contenttype'),(16,'Can view content type',4,'view_contenttype'),(17,'Can add session',5,'add_session'),(18,'Can change session',5,'change_session'),(19,'Can delete session',5,'delete_session'),(20,'Can view session',5,'view_session'),(21,'Can add student',6,'add_student'),(22,'Can change student',6,'change_student'),(23,'Can delete student',6,'delete_student'),(24,'Can view student',6,'view_student'),(25,'Can add subject',7,'add_subject'),(26,'Can change subject',7,'change_subject'),(27,'Can delete subject',7,'delete_subject'),(28,'Can view subject',7,'view_subject'),(29,'Can add teacher',8,'add_teacher'),(30,'Can change teacher',8,'change_teacher'),(31,'Can delete teacher',8,'delete_teacher'),(32,'Can view teacher',8,'view_teacher'),(33,'Can add parent guardian',9,'add_parentguardian'),(34,'Can change parent guardian',9,'change_parentguardian'),(35,'Can delete parent guardian',9,'delete_parentguardian'),(36,'Can view parent guardian',9,'view_parentguardian'),(37,'Can add notification',10,'add_notification'),(38,'Can change notification',10,'change_notification'),(39,'Can delete notification',10,'delete_notification'),(40,'Can view notification',10,'view_notification'),(41,'Can add fee',11,'add_fee'),(42,'Can change fee',11,'change_fee'),(43,'Can delete fee',11,'delete_fee'),(44,'Can view fee',11,'view_fee'),(45,'Can add class assignment',12,'add_classassignment'),(46,'Can change class assignment',12,'change_classassignment'),(47,'Can delete class assignment',12,'delete_classassignment'),(48,'Can view class assignment',12,'view_classassignment'),(49,'Can add audit log',13,'add_auditlog'),(50,'Can change audit log',13,'change_auditlog'),(51,'Can delete audit log',13,'delete_auditlog'),(52,'Can view audit log',13,'view_auditlog'),(53,'Can add assignment',14,'add_assignment'),(54,'Can change assignment',14,'change_assignment'),(55,'Can delete assignment',14,'delete_assignment'),(56,'Can view assignment',14,'view_assignment'),(57,'Can add student assignment',15,'add_studentassignment'),(58,'Can change student assignment',15,'change_studentassignment'),(59,'Can delete student assignment',15,'delete_studentassignment'),(60,'Can view student assignment',15,'view_studentassignment'),(61,'Can add grade',16,'add_grade'),(62,'Can change grade',16,'change_grade'),(63,'Can delete grade',16,'delete_grade'),(64,'Can view grade',16,'view_grade'),(65,'Can add User',17,'add_customuser'),(66,'Can change User',17,'change_customuser'),(67,'Can delete User',17,'delete_customuser'),(68,'Can view User',17,'view_customuser'),(69,'Can add announcement',18,'add_announcement'),(70,'Can change announcement',18,'change_announcement'),(71,'Can delete announcement',18,'delete_announcement'),(72,'Can view announcement',18,'view_announcement'),(73,'Can add report card',19,'add_reportcard'),(74,'Can change report card',19,'change_reportcard'),(75,'Can delete report card',19,'delete_reportcard'),(76,'Can view report card',19,'view_reportcard'),(77,'Can add attendance',20,'add_attendance'),(78,'Can change attendance',20,'change_attendance'),(79,'Can delete attendance',20,'delete_attendance'),(80,'Can view attendance',20,'view_attendance'),(81,'Can add attendance summary',21,'add_attendancesummary'),(82,'Can change attendance summary',21,'change_attendancesummary'),(83,'Can delete attendance summary',21,'delete_attendancesummary'),(84,'Can view attendance summary',21,'view_attendancesummary'),(85,'Can add academic term',22,'add_academicterm'),(86,'Can change academic term',22,'change_academicterm'),(87,'Can delete academic term',22,'delete_academicterm'),(88,'Can view academic term',22,'view_academicterm'),(89,'Can add student attendance',23,'add_studentattendance'),(90,'Can change student attendance',23,'change_studentattendance'),(91,'Can delete student attendance',23,'delete_studentattendance'),(92,'Can view student attendance',23,'view_studentattendance'),(93,'Can add attendance period',24,'add_attendanceperiod'),(94,'Can change attendance period',24,'change_attendanceperiod'),(95,'Can delete attendance period',24,'delete_attendanceperiod'),(96,'Can view attendance period',24,'view_attendanceperiod');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_fee`
--

DROP TABLE IF EXISTS `core_fee`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_fee` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `amount_payable` decimal(10,2) NOT NULL,
  `amount_paid` decimal(10,2) NOT NULL,
  `payment_mode` varchar(10) NOT NULL,
  `payment_status` varchar(10) NOT NULL,
  `payment_date` datetime(6) DEFAULT NULL,
  `receipt_number` varchar(20) NOT NULL,
  `academic_year` varchar(9) NOT NULL,
  `term` smallint unsigned NOT NULL,
  `due_date` date NOT NULL,
  `date_recorded` datetime(6) NOT NULL,
  `last_updated` datetime(6) NOT NULL,
  `student_id` bigint NOT NULL,
  `balance` decimal(10,2) NOT NULL,
  `notes` longtext NOT NULL DEFAULT (_utf8mb3''),
  `recorded_by_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `receipt_number` (`receipt_number`),
  KEY `core_fee_student_id_f7333ba9_fk_core_student_id` (`student_id`),
  KEY `core_fee_recorded_by_id_a23d894b_fk_accounts_customuser_id` (`recorded_by_id`),
  KEY `core_fee_payment_859d8e_idx` (`payment_status`),
  KEY `core_fee_due_dat_31c206_idx` (`due_date`),
  CONSTRAINT `core_fee_recorded_by_id_a23d894b_fk_accounts_customuser_id` FOREIGN KEY (`recorded_by_id`) REFERENCES `accounts_customuser` (`id`),
  CONSTRAINT `core_fee_student_id_f7333ba9_fk_core_student_id` FOREIGN KEY (`student_id`) REFERENCES `core_student` (`id`),
  CONSTRAINT `core_fee_chk_1` CHECK ((`term` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_fee`
--

LOCK TABLES `core_fee` WRITE;
/*!40000 ALTER TABLE `core_fee` DISABLE KEYS */;
INSERT INTO `core_fee` VALUES (6,2000.00,1800.00,'CASH','PARTIAL',NULL,'','2024-2025',3,'2025-06-13','2025-06-16 21:20:43.989599','2025-06-16 21:20:43.989687',5,0.00,'',NULL),(7,2000.00,2000.00,'CASH','PAID','2025-06-16 21:33:48.565455','RCPT250001','2024-2025',3,'2025-06-12','2025-06-16 21:33:48.566299','2025-06-16 21:33:48.566329',6,0.00,'',NULL),(8,2000.00,2100.00,'CASH','PAID','2025-06-16 21:40:05.901417','RCPT250002','2024-2025',2,'2025-06-05','2025-06-16 21:40:05.902010','2025-06-16 21:40:05.902041',6,0.00,'',NULL),(9,3000.00,3000.00,'CARD','PAID','2025-06-16 21:51:39.840584','RCPT250003','2024-2025',2,'2025-06-11','2025-06-16 21:51:39.841626','2025-06-16 21:51:39.841690',5,0.00,'',NULL),(11,4000.00,4000.00,'BANK','PAID','2025-06-18 11:19:11.386057','RCPT250004','2024-2025',1,'2025-06-14','2025-06-18 11:19:11.386726','2025-06-18 11:19:11.386756',5,0.00,'',NULL),(12,2000.00,2000.00,'CHECK','PAID','2025-06-21 18:57:49.334994','RCPT250005','2024-2025',1,'2025-06-20','2025-06-21 18:57:49.335591','2025-06-21 18:57:49.335620',7,0.00,'',NULL);
/*!40000 ALTER TABLE `core_fee` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_feecategory`
--

DROP TABLE IF EXISTS `core_feecategory`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_feecategory` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` longtext NOT NULL,
  `is_mandatory` tinyint(1) NOT NULL,
  `applies_to_all` tinyint(1) NOT NULL,
  `class_levels` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_feecategory`
--

LOCK TABLES `core_feecategory` WRITE;
/*!40000 ALTER TABLE `core_feecategory` DISABLE KEYS */;
INSERT INTO `core_feecategory` VALUES (1,'Tuition','Standard tuition fee',1,1,'');
/*!40000 ALTER TABLE `core_feecategory` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_feepayment`
--

DROP TABLE IF EXISTS `core_feepayment`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_feepayment` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `amount` decimal(10,2) NOT NULL,
  `payment_date` datetime(6) NOT NULL,
  `payment_mode` varchar(10) NOT NULL,
  `receipt_number` varchar(20) NOT NULL,
  `notes` longtext NOT NULL,
  `bank_reference` varchar(50) NOT NULL,
  `is_confirmed` tinyint(1) NOT NULL,
  `fee_id` bigint NOT NULL,
  `recorded_by_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `receipt_number` (`receipt_number`),
  KEY `core_feepayment_fee_id_48323609_fk_core_fee_id` (`fee_id`),
  KEY `core_feepayment_recorded_by_id_038894bb_fk_accounts_` (`recorded_by_id`),
  CONSTRAINT `core_feepayment_recorded_by_id_038894bb_fk_accounts_` FOREIGN KEY (`recorded_by_id`) REFERENCES `accounts_customuser` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_feepayment`
--

LOCK TABLES `core_feepayment` WRITE;
/*!40000 ALTER TABLE `core_feepayment` DISABLE KEYS */;
/*!40000 ALTER TABLE `core_feepayment` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_notification`
--

DROP TABLE IF EXISTS `core_notification`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_notification` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `notification_type` varchar(10) NOT NULL,
  `title` varchar(200) NOT NULL,
  `message` longtext NOT NULL,
  `related_object_id` int unsigned DEFAULT NULL,
  `related_content_type` varchar(50) NOT NULL,
  `is_read` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `recipient_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `core_notification_recipient_id_24a3d95c_fk_accounts_` (`recipient_id`),
  CONSTRAINT `core_notification_recipient_id_24a3d95c_fk_accounts_` FOREIGN KEY (`recipient_id`) REFERENCES `accounts_customuser` (`id`),
  CONSTRAINT `core_notification_chk_1` CHECK ((`related_object_id` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_notification`
--

LOCK TABLES `core_notification` WRITE;
/*!40000 ALTER TABLE `core_notification` DISABLE KEYS */;
INSERT INTO `core_notification` VALUES (1,'GRADE','school grade is at the notice','kindly  go  to the notice board for grade update',1,'',1,'2025-07-01 01:00:22.474833',14);
/*!40000 ALTER TABLE `core_notification` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_parentguardian`
--

DROP TABLE IF EXISTS `core_parentguardian`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_parentguardian` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `full_name` varchar(200) NOT NULL,
  `occupation` varchar(100) NOT NULL,
  `relationship` varchar(1) NOT NULL,
  `phone_number` varchar(20) NOT NULL,
  `email` varchar(254) NOT NULL,
  `address` longtext NOT NULL,
  `is_emergency_contact` tinyint(1) NOT NULL,
  `emergency_contact_priority` smallint unsigned NOT NULL,
  `student_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `core_parentguardian_student_id_caec4680_fk_core_student_id` (`student_id`),
  CONSTRAINT `core_parentguardian_student_id_caec4680_fk_core_student_id` FOREIGN KEY (`student_id`) REFERENCES `core_student` (`id`),
  CONSTRAINT `core_parentguardian_chk_1` CHECK ((`emergency_contact_priority` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_parentguardian`
--

LOCK TABLES `core_parentguardian` WRITE;
/*!40000 ALTER TABLE `core_parentguardian` DISABLE KEYS */;
INSERT INTO `core_parentguardian` VALUES (1,'Mr. Abraham','farmer','F','0547855414','abraham@gmail.com','DUNKWA-ATECHEM',1,1,5),(2,'Mr. Abraham','farmer','F','0245586458','abraham@gmail.com','',1,1,6),(3,'SANDRA ARTHUR','farmer','M','0245589642','sark@gmail.com','POWERLINE',1,2,5),(4,'sandra','farmer','M','0245589425','menssa@gmail.com','abesewa',1,1,7);
/*!40000 ALTER TABLE `core_parentguardian` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_student`
--

DROP TABLE IF EXISTS `core_student`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_student` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `student_id` varchar(20) NOT NULL,
  `first_name` varchar(100) NOT NULL,
  `middle_name` varchar(100) NOT NULL,
  `last_name` varchar(100) NOT NULL,
  `date_of_birth` date NOT NULL,
  `gender` varchar(1) NOT NULL,
  `nationality` varchar(100) NOT NULL,
  `ethnicity` varchar(100) NOT NULL,
  `religion` varchar(100) NOT NULL,
  `place_of_birth` varchar(100) NOT NULL,
  `residential_address` longtext NOT NULL,
  `profile_picture` varchar(100) DEFAULT NULL,
  `class_level` varchar(2) NOT NULL,
  `admission_date` date NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `student_id` (`student_id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `core_student_user_id_666ccffd_fk_accounts_customuser_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_customuser` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_student`
--

LOCK TABLES `core_student` WRITE;
/*!40000 ALTER TABLE `core_student` DISABLE KEYS */;
INSERT INTO `core_student` VALUES (5,'STU0001','Kofi','','Abraham','2016-01-15','M','GHANAIAN','DAGOMBA','CHRISTIAN','walewale','walewale PO Box 45','students/STU0001.jpg','P1','2025-06-09',1,13),(6,'STU0002','Yaw','','Abraham','2017-06-08','M','GHANAIAN','DAGOMBA','CHRISTIAN','Admin_Sch','walewale PO Box 45','students/STU0002.jpg','P2','2025-06-11',1,15),(7,'STU0003','John','','Mensah','2008-02-21','M','GHANAIAN','','CHRISTIAN','walewale','WALEWALE','students/STU0003.jpg','J3','2025-06-21',1,17);
/*!40000 ALTER TABLE `core_student` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_subject`
--

DROP TABLE IF EXISTS `core_subject`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_subject` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `code` varchar(10) NOT NULL,
  `description` longtext NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_subject`
--

LOCK TABLES `core_subject` WRITE;
/*!40000 ALTER TABLE `core_subject` DISABLE KEYS */;
INSERT INTO `core_subject` VALUES (1,'Mathematics','M1','CORE SUBJECT'),(2,'ENGLISH','E1','CORE SUBJECT'),(3,'SCIENCE','SCI 01','Core subject'),(4,'ICT','ICT01','Core subject'),(5,'RME','RM-001','');
/*!40000 ALTER TABLE `core_subject` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_teacher`
--

DROP TABLE IF EXISTS `core_teacher`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_teacher` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `first_name` varchar(100) NOT NULL,
  `last_name` varchar(100) NOT NULL,
  `date_of_birth` date NOT NULL,
  `gender` varchar(1) NOT NULL,
  `phone_number` varchar(20) NOT NULL,
  `email` varchar(254) NOT NULL,
  `address` longtext NOT NULL,
  `class_levels` varchar(50) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `core_teacher_user_id_0d56ab99_fk_accounts_customuser_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_customuser` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_teacher`
--

LOCK TABLES `core_teacher` WRITE;
/*!40000 ALTER TABLE `core_teacher` DISABLE KEYS */;
INSERT INTO `core_teacher` VALUES (5,'Clement','Eshun','1990-06-21','M','0547895145','clement@gmail.com','DUNKWA-ATECHEM','P1',1,14),(6,'Solomon','Adjei','1999-02-10','M','0245845621','mensah@gmail.com','BOX 22 Central SDA Church Kintampo','JHS 1, JHS 2',1,16);
/*!40000 ALTER TABLE `core_teacher` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_teacher_subjects`
--

DROP TABLE IF EXISTS `core_teacher_subjects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_teacher_subjects` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `teacher_id` bigint NOT NULL,
  `subject_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `core_teacher_subjects_teacher_id_subject_id_d0c3c778_uniq` (`teacher_id`,`subject_id`),
  KEY `core_teacher_subjects_subject_id_20be280c_fk_core_subject_id` (`subject_id`),
  CONSTRAINT `core_teacher_subjects_subject_id_20be280c_fk_core_subject_id` FOREIGN KEY (`subject_id`) REFERENCES `core_subject` (`id`),
  CONSTRAINT `core_teacher_subjects_teacher_id_c7d52cc5_fk_core_teacher_id` FOREIGN KEY (`teacher_id`) REFERENCES `core_teacher` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_teacher_subjects`
--

LOCK TABLES `core_teacher_subjects` WRITE;
/*!40000 ALTER TABLE `core_teacher_subjects` DISABLE KEYS */;
INSERT INTO `core_teacher_subjects` VALUES (5,5,2),(6,6,5);
/*!40000 ALTER TABLE `core_teacher_subjects` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_admin_log`
--

DROP TABLE IF EXISTS `django_admin_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_accounts_customuser_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_accounts_customuser_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_customuser` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=56 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_admin_log`
--

LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
INSERT INTO `django_admin_log` VALUES (25,'2025-06-09 16:07:27.106761','1','Admin_School',3,'',17,12),(26,'2025-06-09 16:07:27.281036','5','clement',3,'',17,12),(27,'2025-06-09 16:07:27.448816','11','Joshua_',3,'',17,12),(28,'2025-06-09 16:07:27.550398','4','STU-001',3,'',17,12),(29,'2025-06-09 16:07:27.786889','2','STU-002',3,'',17,12),(30,'2025-06-09 16:07:28.232853','7','STU-003',3,'',17,12),(31,'2025-06-09 16:07:28.467018','9','STU-004',3,'',17,12),(32,'2025-06-09 16:07:28.653756','3','teacher_abraham@gmail.com',3,'',17,12),(33,'2025-06-09 16:07:28.803458','8','teacher_emmanuel@gmail.com',3,'',17,12),(34,'2025-06-09 16:07:28.956094','10','teacher_robertdanso@gmail.com',3,'',17,12),(35,'2025-06-09 16:07:52.361086','6','Abraham',3,'',17,12),(36,'2025-06-09 17:54:32.301429','14','teacher_clement@gmail.com',2,'[{\"changed\": {\"fields\": [\"User permissions\", \"Last login\"]}}]',17,12),(37,'2025-06-09 17:59:14.958741','14','clement_esh',2,'[{\"changed\": {\"fields\": [\"Username\", \"Email address\", \"Phone number\", \"Address\", \"Date of birth\"]}}]',17,12),(38,'2025-06-09 21:59:52.043930','12','Admin_Sch',2,'[{\"changed\": {\"fields\": [\"User permissions\"]}}]',17,12),(39,'2025-06-09 22:01:29.011695','12','Admin_Sch',2,'[{\"changed\": {\"fields\": [\"Active\", \"Staff status\"]}}]',17,12),(40,'2025-06-09 22:03:34.156256','12','Admin_Sch',2,'[{\"changed\": {\"fields\": [\"Active\", \"Staff status\"]}}]',17,14),(41,'2025-06-11 14:27:42.382032','14','clement_esh',2,'[{\"changed\": {\"fields\": [\"Groups\"]}}]',17,12),(42,'2025-07-01 00:07:11.860067','1','Term 1 2024-2025',1,'[{\"added\": {}}]',22,12),(43,'2025-07-01 00:07:42.872674','1','Daily (2025-07-01 to 2025-07-01)',1,'[{\"added\": {}}]',24,12),(44,'2025-07-01 00:09:13.371486','2','Term 2 2024-2025',1,'[{\"added\": {}}]',22,12),(45,'2025-07-01 00:21:22.345253','1','John  Mensah (STU0003) - JHS 3 - 2025-07-01 - Present',1,'[{\"added\": {}}]',23,12),(46,'2025-07-01 00:37:45.886873','3','Yaw  Abraham (STU0002) - Primary 2 - ICT (ICT01) (2024/2025 Term 1): D',1,'[{\"added\": {}}]',16,12),(47,'2025-07-01 00:38:49.693262','2','Kofi  Abraham (STU0001) - Primary 1 - ENGLISH (E1) (2024/2025 Term 1): D',2,'[{\"changed\": {\"fields\": [\"Homework score\", \"Classwork score\", \"Test score\", \"Exam score\", \"Remarks\"]}}]',16,12),(48,'2025-07-01 00:44:26.633060','1','Kofi  Abraham (STU0001) - Primary 1 - ENGLISH (E1) (2024-2025 Term 1): E',3,'',16,12),(49,'2025-07-01 00:45:49.805330','2','Kofi  Abraham (STU0001) - Primary 1 - ENGLISH (E1) (2024/2025 Term 1): D',2,'[{\"changed\": {\"fields\": [\"Homework score\", \"Classwork score\", \"Test score\", \"Exam score\"]}}]',16,12),(50,'2025-07-01 00:52:10.416305','1','John  Mensah (STU0003) - JHS 3 - Daily - 91.30434782608695%',1,'[{\"added\": {}}]',21,12),(51,'2025-07-01 00:56:46.309651','9','Primary 4 - SCIENCE (SCI 01) (2024-2025)',1,'[{\"added\": {}}]',12,12),(52,'2025-07-01 00:58:27.283517','2','Kofi  Abraham (STU0001) - Primary 1 - ENGLISH (E1) (2024/2025 Term 1): D',2,'[{\"changed\": {\"fields\": [\"Classwork score\"]}}]',16,12),(53,'2025-07-01 01:00:22.937044','1','Grade Update - school grade is at the notice',1,'[{\"added\": {}}]',10,12),(54,'2025-07-01 01:12:13.512098','1','Kofi  Abraham (STU0001) - Primary 1\'s Report Card - 2024/2025 Term 1',1,'[{\"added\": {}}]',19,12),(55,'2025-07-01 01:18:17.256721','2','Kofi  Abraham (STU0001) - Primary 1 - ENGLISH (E1) (2024/2025 Term 1): D+',2,'[{\"changed\": {\"fields\": [\"Homework score\", \"Classwork score\", \"Test score\"]}}]',16,12);
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_content_type`
--

DROP TABLE IF EXISTS `django_content_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_content_type`
--

LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES (17,'accounts','customuser'),(1,'admin','logentry'),(3,'auth','group'),(2,'auth','permission'),(4,'contenttypes','contenttype'),(22,'core','academicterm'),(18,'core','announcement'),(14,'core','assignment'),(20,'core','attendance'),(24,'core','attendanceperiod'),(21,'core','attendancesummary'),(13,'core','auditlog'),(12,'core','classassignment'),(11,'core','fee'),(16,'core','grade'),(10,'core','notification'),(9,'core','parentguardian'),(19,'core','reportcard'),(6,'core','student'),(15,'core','studentassignment'),(23,'core','studentattendance'),(7,'core','subject'),(8,'core','teacher'),(5,'sessions','session');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_migrations`
--

DROP TABLE IF EXISTS `django_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2025-05-02 00:28:16.233099'),(2,'contenttypes','0002_remove_content_type_name','2025-05-02 00:28:24.685939'),(3,'auth','0001_initial','2025-05-02 00:28:59.535316'),(4,'auth','0002_alter_permission_name_max_length','2025-05-02 00:29:05.142391'),(5,'auth','0003_alter_user_email_max_length','2025-05-02 00:29:05.429425'),(6,'auth','0004_alter_user_username_opts','2025-05-02 00:29:05.688760'),(7,'auth','0005_alter_user_last_login_null','2025-05-02 00:29:06.054686'),(8,'auth','0006_require_contenttypes_0002','2025-05-02 00:29:06.268001'),(9,'auth','0007_alter_validators_add_error_messages','2025-05-02 00:29:06.467396'),(10,'auth','0008_alter_user_username_max_length','2025-05-02 00:29:06.773220'),(11,'auth','0009_alter_user_last_name_max_length','2025-05-02 00:29:07.072258'),(12,'auth','0010_alter_group_name_max_length','2025-05-02 00:29:07.605443'),(13,'auth','0011_update_proxy_permissions','2025-05-02 00:29:07.926683'),(14,'auth','0012_alter_user_first_name_max_length','2025-05-02 00:29:08.132635'),(15,'accounts','0001_initial','2025-05-02 00:29:31.507696'),(16,'admin','0001_initial','2025-05-02 00:29:40.548713'),(17,'admin','0002_logentry_remove_auto_add','2025-05-02 00:29:40.786620'),(18,'admin','0003_logentry_add_action_flag_choices','2025-05-02 00:29:41.110652'),(19,'core','0001_initial','2025-05-02 00:31:08.533792'),(20,'sessions','0001_initial','2025-05-02 00:31:11.795639');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_session`
--

DROP TABLE IF EXISTS `django_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_session`
--

LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
INSERT INTO `django_session` VALUES ('gr892zy6r1lp33usp8rnpvzivkw5k92d','.eJxVjDsOwjAQBe_iGlle_6Gkzxms3bWDA8iR4qRC3B0ipYD2zcx7iYTbWtPWy5KmLC4CQJx-R0J-lLaTfMd2myXPbV0mkrsiD9rlMOfyvB7u30HFXr81mZIjkQHSim10wNEZRex9AM_eOLQjM6uAGIx3-hw1GLI4goqleBbvDwS-N-w:1uGkg5:ic4QCp6bbYImRM87iw8WsT5SsuEa5F7MVSa1oJsuxCE','2025-06-01 20:32:09.979927'),('j3oqed7qvc9scn39xpjfkiyqxwygzkkf','.eJxVzM0OwiAQBOB34WwIP6VQj959BrLLslI1NCntyfjuStKDXuebmZeIsG8l7i2vcSZxFtqI02-IkB65dqE71Nsi01K3dUbZK_LQJq8L5efl6P4dFGjlu3YDex1gAM7BTxPbkVxQOVDyRrMNgIg6eeU6U-rGZFW2OLJxKon3BxDVOHk:1uWyAc:G2TWlq9n-WobIK_ilblkwvTi66WZkbuv5hYjuAzve9Y','2025-07-16 14:10:42.768808');
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-07-02  8:45:11

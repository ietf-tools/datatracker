# Copyright The IETF Trust 2018-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import migrations


def backfill_old_meetings(apps, schema_editor):
        Meeting          = apps.get_model('meeting', 'Meeting')

        for id, number, type_id, date, city, country, time_zone, continent, attendees in [
                ( 59,'59','ietf','2004-03-29','Seoul','KR','Asia/Seoul','Asia','1390' ),
                ( 58,'58','ietf','2003-11-09','Minneapolis','US','America/Menominee','America','1233' ),
                ( 57,'57','ietf','2003-07-13','Vienna','AT','Europe/Vienna','Europe','1304' ),
                ( 56,'56','ietf','2003-03-16','San Francisco','US','America/Los_Angeles','America','1679' ),
                ( 55,'55','ietf','2002-11-17','Atlanta','US','America/New_York','America','1570' ),
                ( 54,'54','ietf','2002-07-14','Yokohama','JP','Asia/Tokyo','Asia','1885' ),
                ( 53,'53','ietf','2002-03-17','Minneapolis','US','America/Menominee','America','1656' ),
                ( 52,'52','ietf','2001-12-09','Salt Lake City','US','America/Denver','America','1691' ),
                ( 51,'51','ietf','2001-08-05','London','GB','Europe/London','Europe','2226' ),
                ( 50,'50','ietf','2001-03-18','Minneapolis','US','America/Menominee','America','1822' ),
                ( 49,'49','ietf','2000-12-10','San Diego','US','America/Los_Angeles','America','2810' ),
                ( 48,'48','ietf','2000-07-31','Pittsburgh','US','America/New_York','America','2344' ),
                ( 47,'47','ietf','2000-03-26','Adelaide','AU','Australia/Adelaide','Australia','1431' ),
                ( 46,'46','ietf','1999-11-07','Washington','US','America/New_York','America','2379' ),
                ( 45,'45','ietf','1999-07-11','Oslo','NO','Europe/Oslo','Europe','1710' ),
                ( 44,'44','ietf','1999-03-14','Minneapolis','US','America/Menominee','America','1705' ),
                ( 43,'43','ietf','1998-12-07','Orlando','US','America/New_York','America','2124' ),
                ( 42,'42','ietf','1998-08-24','Chicago','US','America/Chicago','America','2106' ),
                ( 41,'41','ietf','1998-03-30','Los Angeles','US','America/Los_Angeles','America','1775' ),
                ( 40,'40','ietf','1997-12-08','Washington','US','America/New_York','America','1897' ),
                ( 39,'39','ietf','1997-08-11','Munich','DE','Europe/Berlin','Europe','1308' ),
                ( 38,'38','ietf','1997-04-07','Memphis','US','America/Chicago','America','1321' ),
                ( 37,'37','ietf','1996-12-09','San Jose','US','America/Los_Angeles','America','1993' ),
                ( 36,'36','ietf','1996-06-24','Montreal','CA','America/New_York','America','1283' ),
                ( 35,'35','ietf','1996-03-04','Los Angeles','US','America/Los_Angeles','America','1038' ),
                ( 34,'34','ietf','1995-12-04','Dallas','US','America/Chicago','America','1007' ),
                ( 33,'33','ietf','1995-07-17','Stockholm','SE','Europe/Stockholm','Europe','617' ),
                ( 32,'32','ietf','1995-04-03','Danvers','US','America/New_York','America','983' ),
                ( 31,'31','ietf','1994-12-05','San Jose','US','America/Los_Angeles','America','1079' ),
                ( 30,'30','ietf','1994-07-25','Toronto','CA','America/New_York','America','710' ),
                ( 29,'29','ietf','1994-03-28','Seattle','US','America/Los_Angeles','America','785' ),
                ( 28,'28','ietf','1993-11-01','Houston','US','America/Chicago','America','636' ),
                ( 27,'27','ietf','1993-07-12','Amsterdam','NL','Europe/Amsterdam','Europe','493' ),
                ( 26,'26','ietf','1993-03-29','Columbus','US','America/New_York','America','638' ),
                ( 25,'25','ietf','1992-11-16','Washington','US','America/New_York','America','633' ),
                ( 24,'24','ietf','1992-07-13','Cambridge','US','America/New_York','America','677' ),
                ( 23,'23','ietf','1992-03-16','San Diego','US','America/Los_Angeles','America','530' ),
                ( 22,'22','ietf','1991-11-18','Santa Fe','US','America/Denver','America','372' ),
                ( 21,'21','ietf','1991-07-29','Atlanta','US','America/New_York','America','387' ),
                ( 20,'20','ietf','1991-03-11','St. Louis','US','America/Chicago','America','348' ),
                ( 19,'19','ietf','1990-12-03','Boulder','US','America/Denver','America','292' ),
                ( 18,'18','ietf','1990-07-30','Vancouver','CA','America/Los_Angeles','America','293' ),
                ( 17,'17','ietf','1990-05-01','Pittsburgh','US','America/New_York','America','244' ),
                ( 16,'16','ietf','1990-02-06','Tallahassee','US','America/New_York','America','196' ),
                ( 15,'15','ietf','1989-10-31','Honolulu','US','Pacific/Honolulu','America','138' ),
                ( 14,'14','ietf','1989-07-25','Stanford','US','America/Los_Angeles','America','217' ),
                ( 13,'13','ietf','1989-04-11','Cocoa Beach','US','America/New_York','America','114' ),
                ( 12,'12','ietf','1989-01-18','Austin','US','America/Chicago','America','120' ),
                ( 11,'11','ietf','1988-10-17','Ann Arbor','US','America/New_York','America','114' ),
                ( 10,'10','ietf','1988-06-15','Annapolis','US','America/New_York','America','112' ),
                ( 9,'9','ietf','1988-03-01','San Diego','US','America/Los_Angeles','America','82' ),
                ( 8,'8','ietf','1987-11-02','Boulder','US','America/Denver','America','56' ),
                ( 7,'7','ietf','1987-07-27','McLean','US','America/New_York','America','101' ),
                ( 6,'6','ietf','1987-04-22','Boston','US','America/New_York','America','88' ),
                ( 5,'5','ietf','1987-02-04','Moffett Field','US','America/Los_Angeles','America','35' ),
                ( 4,'4','ietf','1986-10-15','Menlo Park','US','America/Los_Angeles','America','35' ),
                ( 3,'3','ietf','1986-07-23','Ann Arbor','US','America/New_York','America','18' ),
                ( 2,'2','ietf','1986-04-08','Aberdeen','US','America/New_York','America','21' ),
                ( 1,'1','ietf','1986-01-16','San Diego','US','America/Los_Angeles','America','21' ),
        ]:
            Meeting.objects.get_or_create(id=id, number=number, type_id=type_id,
                                          date=date, city=city, country=country,
                                          time_zone=time_zone);


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0004_meeting_attendees'),
    ]

    operations = [
        migrations.RunPython(backfill_old_meetings, reverse)
    ]
            

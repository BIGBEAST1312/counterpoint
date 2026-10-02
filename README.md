# Counterpoint

**Product Description  
CMPT 370 · University of Saskatchewan**

## Section 1: Project Details

**Group Name:**  "We'll Study It Later"     
**Teaching Assistant:** Palash

#	Name	Role	Email	NSID
1	Patel Aarya	Team lead	pcq713@usask.ca	pcq713
2	Patel Haryan	Member	bwr045@usask.ca	bwr045
3	Patel Hetank	Member	fjw827@usask.ca	fjw827
4	Sawant Mohit	Member	cwf024@usask.ca	cwf024
5	Patel Priyesh	Member	orv018@usask.ca	orv018

## Section 2: Product Description

**Product Name:** Counterpoint

Product description: Counterpoint is a walk-up queue and visit record for the USask IT Support desk at Murray Library. Its essential features are kiosk check-in with a ticket number and estimated wait, a live staff queue for calling students to the desk's two stations, a lobby screen that shows ticket numbers instead of names, a TeamDynamix ticket draft built from each finished visit, staff presence (on desk, on break, at lunch), a coverage page for library staff, and weekly statistics on waits and busy hours.

Need and value: Today students just form a line, with no record of who came first and no idea how long they'll wait. Assistants write tickets from memory long after the student has left, and desk coverage is tracked by posting in a Teams chat. TeamDynamix records tickets but not the line itself. Counterpoint records the line, cuts ticket-writing time, and gives the supervisor real wait and arrival data to staff the desk.

Stakeholders: students who walk up for help; IT Support student assistants; the IT Support desk supervisor; Murray Library evening and weekend staff, who need to know whether the desk is covered; and USask IT Support Services and the ICT manager, who care about service levels without using the system directly. Our stakeholders are USask IT Support Services and Jeenay, a USask Computer Science student who isn't in this course.

Technology requirements: for development, Python 3.11+ with FastAPI, SQLite through SQLAlchemy, WebSockets for live updates, plain HTML, CSS and JavaScript, pytest, and GitLab for the wiki, issue board, merge requests and CI. For the deployed product, one small web server on the university network running the FastAPI app with its database, opened in a browser on a check-in tablet, the desk computers and a lobby display. It needs no student accounts and no connection to TeamDynamix.

## Section 3: Use of AI

We used Claude (Anthropic) to know which technologies are requried other than python, HTML and CSS.
# AnnotationTool

## Development Server

We now have a development Server which serves as a showcase of the current state of the project.

The adress is: [http://193.196.54.251](http://193.196.54.251)

### Current Users

#### admin
- can log in to the admin page where all the adding of project, batches, users etc. happens. This is available on [http://193.196.54.251/admin](http://193.196.54.251/admin). If you are not logged in, you might are currently referred to the wrong page, so you might have to use the link twice.
- has role "Superuser"
- has role "is_staff"
- has no groups

#### annotator1
- default annotator without special permissions
- has group "Annotator"

#### annotator2
- same as annotator1. Exists because we want 2 annotators for each project
- has group "Annotator"

#### expert1

- A role to show the expert interface.

- has group "Admin"
- has group "Expert"

### expert2

- A second expert that has the additional role of Annotator.
- For now, expert2 should behave the same as expert1

- has group "Admin"
- has group "Annotator"
- has group "Expert"

### Passwords

every user has a password of "123".

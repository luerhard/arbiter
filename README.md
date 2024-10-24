# AnnotationTool

## Keyboard Shortcuts

For the Annotation phase, some keyboard shortcuts are implemented.

- Left Arrow Key: Go backwards through the samples (sentences)
- Right Arrow Key: Go to the next sample (sentence)
- Number keys: The number in parentheses behind the label can be used to toggle the annotation.
- Up Arrow and Enter Key: Can be used to saved the annotation (send the latest state of all labels to the server)

## Development Server

We now have a development Server which serves as a showcase of the current state of the project.

The adress is: [http://193.196.54.251](http://193.196.54.251)

To access it, you need to be in the University of Stuttgart VPN (or physically on campus).

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

## Steps with explanation to run the web application locally 
- #### cd core: 
This command changes the current working directory to the core folder, where the main project files are likely stored. It's essential to navigate to the correct directory before running any project-specific commands.

- #### npm install: 
This installs all the Node.js dependencies listed in the package.json file. These dependencies include libraries and frameworks that the web application needs to run, such as React, Webpack, or other JavaScript modules.

- #### poetry install: 
This command installs all the Python dependencies specified in the pyproject.toml file using Poetry, a dependency management tool for Python. It ensures that all the required libraries and frameworks are available for the backend.

- #### npm start: 
This runs the development server for the frontend, defined in the package.json file under the start script. It typically starts a local server (like webpack-dev-server) to serve the frontend assets and enable live reloading for development. If you keep this running in a seperate terminal, it will continuously monitor the files for changes and reload upon changes (see Some insights on Webpack with --watch Option below)

- #### python manage.py runserver: 
This command starts the Django development server on a local machine, allowing you to access the backend of the web application in your browser. It serves the API and the backend logic necessary for the application to function.

- #### test the web application
You can typically access the django server with a local url like http://127.0.0.1:8000/ (this will be output in your terminal). If you want to test it using the users created for the development server, you need to copy the database from the development server to your local directory. To get the right version, it is best to ask Lukas for it.



## Some insights on Webpack with --watch Option
Webpack is a powerful module bundler for JavaScript applications. The --watch option in Webpack is used to keep the build process running in the background, watching for any changes in the source files. When a file is modified, Webpack automatically recompiles the changes, which is useful for speeding up the development process by providing near-instant feedback on changes.





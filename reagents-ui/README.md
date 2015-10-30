# Reagent registration UI

Based on the angular seed project (https://github.com/angular/angular-seed)

## Front-end
AngularJS app contained primarily in the `app` directory. Most files in this root are also project management files for the front-end.

## Back-end
Simple flask-based (Python) API proxy exporting a small subset of the Genologics API for reagent registration.

  - reagents.conf: Apache configuration file
  - reagents.wsgi: WSGI app file.
  - backend/api.py: Backend code

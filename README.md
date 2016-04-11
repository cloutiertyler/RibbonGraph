# RibbonGraph
A Declarative Graph API Django App

RibbonGraph is a Django app which provides a declarative permission layer to a
Neo4j database. It is perfect for building social networking applications.

The RibbonGraph philosophy is that a social graph is a shared resource for all
the users that has rules about how the users are allowed to use the graph.

Therefore all that's required to have a social network is a declaration those
rules. This is what RibbonGraph provides.

Requirements
------------
As of now this app is meant for use with the [djangorestframework](http://www.django-rest-framework.org) and it uses that projects base class APIException for all GraphAPIErrors.

Quick start
-----------

1. Run
        pip install ribbon-graph
2. Add "ribbon" to your INSTALLED_APPS setting like this:

        INSTALLED_APPS = [
            ...
           'ribbon',
        ]

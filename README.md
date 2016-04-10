# RibbonGraph
A Declarative Python Graph API

RibbonGraph is a Django app which provides a declarative permission layer to a
Neo4j database. It is perfect for building social networking applications.

The RibbonGraph philosophy is that a social graph is a shared resource for all
the users that has rules about how the users are allowed to use the graph.

Therefore all that's required to have a social network is a declaration those
rules. This is what RibbonGraph provides.

Quick start
-----------

1. Add "ribbon" to your INSTALLED_APPS setting like this:

    INSTALLED_APPS = [
        ...
        'ribbon',
    ]

2. That's it.

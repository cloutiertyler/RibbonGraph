# RibbonGraph
A Declarative Graph API Django App

RibbonGraph is a Django app which provides a declarative permission layer to a
Neo4j database. It is perfect for building social networking applications.

The RibbonGraph philosophy is that a social graph is a shared resource for all
the users that has rules about how the users are allowed to use the graph.

Therefore all that's required to have a social network is a declaration those
rules. This is what RibbonGraph provides.

> Why the name RibbonGraph? 

> Well the idea is that RibbonGraph wraps all the potentially very complicated logic of social network into a neat little package.

User Guide
----------
RibbonGraph will allow you to simplify all of your API endpoints down to just a few. The example below demonstrates the power of RibbonGraph. Here we are using django-rest-framework's APIView class to create a NodeView.

    class NodeView(APIView):
        authentication_classes = (TokenAuthentication, )
        permission_classes = (IsAuthenticated, )

        def get(self, request, node_type=None, id=None):
            """
            Returns a json object representing the tree of graph nodes rooted at the node
            with identifier `id` or if no `id` is specified a list of trees rooted at the
            nodes that meet the query constraints.
            """
            user = request.user
            api = GraphAPI(settings.NEO4J_URL, models=model_list)
            query_dict = get_query_dict_from_params(request.query_params)
            if id:
                id = int(id)
                response_data = api.request_subgraph_at_node(user.id, query_dict.get('include', None), id)
            else:
                response_data = api.query_for_subgraphs(user.id, query_dict, node_type)
            return Response(response_data)

        def put(self, request, id):
            """
            Applies the tree updated rooted at the node with the identifier `id`.
            """
            user = request.user
            api = GraphAPI(settings.NEO4J_URL, models=model_list)
            update_dict = request.data
            id = int(id)
            response_data = api.update_subgraph_at_node(user.id, 'update', update_dict, id)
            return Response(response_data)


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

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

The GET endpoint defined above let's the client query for arbirary subtrees in the graph with a single request.
Now there is no need for multiple round trips to different API endpoints. No complicated APIs or need for batching requests.

For example when a user logs in you can request all of the user's information, plus all of their friends' information and even their friends' friends' information. The granularity of the request is down to the field level.

Let's look at what that request might look like:

        https://my-app.com/nodes/23432?include=first_name,last_name,friends.include(first_name,last_name),received_friend_requests.include(sender,receiver)

With is one call we are able to get all the friends and friend requests of user `23432` with a single request. Best of all we can easily add or remove fields extremely easily. This makes debugging and development significantly faster.

We can create a similar POST endpoint that allows clients to create nodes in the graph. An update in this case is specified as JSON in the request body.

        def post(self, request, node_type):
            """
            Applies the tree update rooted at the node being created.
            """
            user = request.user
            api = GraphAPI(settings.NEO4J_URL, models=model_list)
            create_dict = request.data
            response_data = api.update_subgraph_at_node(user.id, 'create', create_dict, node_type=node_type)
            return Response(response_data)

The syntax for updates is very similar to the syntax for GET requests, with some small differences. Here's what sending a friend request might look like.

url:
    https://my-app.com/nodes/FriendRequest

body:
    {
        "sender":{
            "attach":{
                "id":23432
            }
        },
        "receiver":{
            "attach":{
                "id":83472
            }
        },
        "receiver_has_seen":false
    }
    
Here we are saying that we'd like to create an object of type FriendRequest and we'd like to attach that to two users, the sender and the receiver.

You may have noticed something is missing, however. That something is permissions.

Permissions
-----------

Permissions are what define your GraphAPI. The philosophy of RibbonGraph is that clients should be able to make any change to the shared graph that they want, *as long as they're allowed*.

And just like that we have a social network.


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

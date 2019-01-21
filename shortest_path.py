
import sys
import argparse
import json
import matplotlib.cbook
import networkx as nx
from networkx.drawing.nx_pydot import write_dot
from networkx.readwrite import json_graph
import shlex
import subprocess
import os
import warnings

warnings.filterwarnings("ignore", category=matplotlib.cbook.mplDeprecation)


"""
Return true if all the cities in the planned $journey exist in the JSON 
topology data, else false.
"""
def check_journey_cities_exist(journey, topology_json):

    cities_in_topology = [
        city['id'] for city in topology_json['nodes'] if city['id'] in journey
    ]

    """
    The start and end city might be the same, check the number of cities
    found in the topology against the number of cities in the set of unique
    cities in the requested journey list.
    """ 
    if len(cities_in_topology) != len(set(journey)):
        print("Not all cities in your journey request journey were found in "
              "the the topology!\n")
        print(
            "Missing: {}\n".format(
                [city for city in journey if city not in cities_in_topology]
            )
        )
        return False
    
    else:
        return True


"""
Return the name of the city which is closet to $city in the list of cities
$journey, and return the path between the closet city in $journey and $city.
"""
def find_closet_neigh_to_city(city, graph, journey):

    closest_neighbour = None
    shortest_path = []

    for location in journey:

        # Don't search for a path from "city" to itself
        if location == city:
            continue

        path = list(nx.nx.shortest_path(graph, source=city, target=location))

        if len(shortest_path) == 0 or len(path) < len(shortest_path):
            closest_neighbour = path[-1]
            shortest_path = path

    return closest_neighbour, shortest_path


"""
Compute all dijkstra shortest paths in the topology.
Return the shortest dijkstra route that includes all the cities in the journey.
Such a route may not exist.
"""
def find_shortest_dijkstra_route(graph, journey):

    """
    all_pairs_dijkstra_path() and all_pairs_dijkstra_path_length both return
    a generator, hense the use of dict().
    """
    all_paths = dict(nx.all_pairs_dijkstra_path(graph))
    all_lengths = dict(nx.all_pairs_dijkstra_path_length(graph))

    if len(all_paths) != len(all_lengths):
        print("Path count is not equal to path length count, "
              "maybe some links are missing a weight?")
        return False

    shortest_path = []
    
    for destination, path in all_paths[journey[0]].items():

        # If all nodes in our journey are in the current path being checked
        if all(node in path for node in journey):

            if (len(shortest_path) == 0) or (len(path) < len(shortest_path)):
                shortest_path = path


    total = 0
    for section in shortest_path:
        total += len(section) - 1

    print("\nShortest dijkstra journey: {} connection(s)".format(total))
    if len(shortest_path) < 1:
        print("No shortest dijkstra path found!\n")
        return False

    else:
        print("{} hop(s) {}\n".format(len(shortest_path) - 1, shortest_path))
        return shortest_path


"""
Return the shotest path which passes through all the cities in $journey,
not necessarily in the order specified in $journey.
"""
def find_shortest_loose_route(graph, journey):

    route = []

    if len(journey[1:-1]) == 0:
        route.append(nx.shortest_path(graph, source=journey[0], target=journey[1]))

    else:

        closest_neighbour, path = find_closet_neigh_to_city(
            journey[0], graph, journey[1:-1]
        )
        route.append(path)
        journey.remove(closest_neighbour)

        while len(journey[1:-1]) > 0:
            closest_neighbour, path = find_closet_neigh_to_city(
                closest_neighbour, graph, journey[1:-1]
            )
            route.append(path)
            journey.remove(closest_neighbour)

        route.append(
            nx.shortest_path(graph, source=closest_neighbour, target=journey[-1])
        )


    total = 0
    for section in route:
        total += len(section) - 1

    print("\nShortest loose journey: {} connection(s)".format(total))
    for section in route:
        print(
            "From {} to {} ({}): {}".format(
                section[0], section[-1], len(section) - 1, section
            )
        )

    return route


"""
Computer every possible route in the JSON topology data, from every city to
every other city. Return the shorted route that contains all the cities in
$journey. This brute force approach should always returns a path unlike the
dijkstra method but can take 2-3 minutes to compute.
"""
def find_shortest_simple_route(graph, journey, topology_json):

    shortest_path = []

    for city in topology_json['nodes']:

        print("                                                \r", end="")
        print("Checking {} -> {}\r".format(journey[0], city['id']), end="")

        ############### FIX THIS HACK: cutoff=11
        all_paths = list(
            nx.all_simple_paths(graph, source=journey[0],target=city['id'], cutoff=11)
        )

        for path in all_paths:

            # If all nodes in our journey are in the current path being checked
            if all(node in path for node in journey):

                if (len(shortest_path) == 0) or (len(path) < len(shortest_path)):
                    shortest_path = path


    total = 0
    for section in shortest_path:
        total += len(section) - 1

    print("\nShortest simple journey: {} connection(s)".format(total))
    if len(shortest_path) < 1:
        print("No shortest simple path found!\n")
        return False

    else:
        print(
            "{} hop(s) {}\n".format(len(shortest_path) - 1, shortest_path)
        )
        return shortest_path


"""
Return the shortest path which passes through all cities in $journey in the
exact order they are specified in $journey.
"""
def find_shortest_strict_route(graph, journey):

    route = []

    for i in range(0, (len(journey) - 1)):

        start = journey[i]
        end = journey[i + 1]

        shortest_path = nx.shortest_path(graph, source=start, target=end)
        route.append(shortest_path)


    total = 0
    for section in route:
        total += len(section) - 1

    print("\nShortest strict journey: {} connection(s)".format(total))
    for section in route:
        print(
            "From {} to {} ({}): {}".format(
                section[0], section[ - 1], len(section) - 1, section
            )
        )

    return route


"""
Generate the topology diagram based upon the graph topology.
"""
def generate_topology_diagram(filename, graph):

    write_dot(graph, filename + '.dot')

    cmd = "fdp -Gsize=100,100 -Gdpi=100 -Gnodesep=equally -Granksep=equally "
    cmd += "-Nshape=circle -Nstyle=filled -Nwidth=2 -Nheight=2 "
    cmd += "-Tpng -o " + shlex.quote(filename) + " " + shlex.quote(filename)
    cmd += ".dot"

    result = subprocess.getstatusoutput(cmd)
    if result[0] != 0:
        print("Error generating pydot fdp file")
        print(result[1])
        return False


    cmd = "rm -f " + shlex.quote(filename) + ".dot"

    result = subprocess.getstatusoutput(cmd)
    if result[0] != 0:
        print("Error deleting pydot dot file")
        print(result[1])
        return False

    return True


"""
Highlight the nodes and edges along the shortest path within the graph,
which will be shown on the topology diagram if generated.
"""
def highlight_shortest_path(graph,shortest_path):

    for section in shortest_path:
        for city in section:
            graph.nodes[city]['fillcolor'] = "lightblue"

        for i in range(0, len(section) - 1):
            graph[section[i]][section[i + 1]]['color'] = "lightblue"
            if graph[section[i]][section[i + 1]]['flight']:
                graph[section[i]][section[i + 1]]['penwidth'] = "15.0"
            else:
                graph[section[i]][section[i + 1]]['penwidth'] = "10.0"

    return


"""
Return the contents of topology JSON file as dict.
"""
def load_topology(filename):

    try:
        topology_file = open(filename, 'r')
    except Exception:
        print("Couldn't open topology file {}".format(filename))
        return False

    try:
        topology_json = json.load(topology_file)
    except Exception as e:
        print("Couldn't parse topology JSON: {}".format(e))
        return False

    topology_file.close()

    return topology_json


def parse_cli_args():

    parser = argparse.ArgumentParser(
        description='Read topology data from a JSON file and produce a '
                    'topology diagram and routing reports.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '-d',
        '--diagram-file',
        help='Output filename of the topology diagram that is generated '
             'showing your shortest path. Provide a blank filename to '
             'disable, e.g. -d ""',
        type=str,
        default='./diagram.png',
    )
    parser.add_argument(
        '-j',
        '--journey',
        help='A comma seperate list of each location you need to visit.',
        type=str,
        default=None,
        required=True,
    )
    parser.add_argument(
        '-p',
        '--print',
        help='Print the list of cities (nodes) in the topology file in '
              'alphabetical order then quit.',
        default=False,
        action='store_true',
        required=False,
    )
    parser.add_argument(
        '-s',
        '--strict',
        help='The default mode is loose mode. In loose mode the comma '
             'seperated journey list if loosely honoured. '
             'The first location is assumed to be your current location, '
             'the last location is assumed to be your final destination, '
             'any cities inbetween may be visited in any order. '
             'When enabling strict mode the comma seperated journey list '
             'is strictly honoured. This means that the list of locations '
             'is followed verbatim.',
        default=False,
        action='store_true',
        required=False,
    )
    parser.add_argument(
        '-t',
        '--topology-file',
        help='JSON topology data file.',
        type=str,
        default='topology.json',
    )
    parser.add_argument(
        '-x',
        help='Try to find extra NetworkX supported shortest path types such as '
             'the dijkstra shortest path and, brute force the simple shortest '
             'path.',
        default=False,
        action='store_true',
        required=False,
    )

    return vars(parser.parse_args())


def print_cities_alphabetical(topology_json):

    print(*sorted([item['id'] for item in topology_json['nodes']]), sep = "\n")


def main():

    args = parse_cli_args()

    # Split the comma seperated list of cities
    journey = args['journey'].split(",")
    if len(journey) < 2:
        print("Journey list too short!\n")
        sys.exit(1)

    # Load a valid topology JSON file
    topology_json = load_topology(args['topology_file'])
    if not topology_json:
        sys.exit(1)

    if args['print']:
        print_cities_alphabetical(topology_json)
        return

    # Check that all the cities in the planned journey exist in the toplogy
    if not check_journey_cities_exist(journey, topology_json):
        sys.exit(1)

    # Create the node/edge graph from the loaded JSON data:
    graph = json_graph.node_link_graph(topology_json)
    print("Graph details:\n{}\n".format(nx.info(graph)))
    if len(graph.nodes) < 3:
        print("{} nodes were loaded from the topology, this is too few!\n")
        sys.exit(1)


    if args['x']:
        find_shortest_dijkstra_route(graph, journey)
        find_shortest_simple_route(graph, journey, topology_json)

    """
    $shortest_path is a list of list. Each list entry is the path between two
    cities along the journey.
    """
    if args['strict']:
        shortest_path = find_shortest_strict_route(graph, journey)
    else:
        shortest_path = find_shortest_loose_route(graph, journey)

    if not shortest_path:
        sys.exit(1)
    

    if args['diagram_file']:
        highlight_shortest_path(graph, shortest_path)
        generate_topology_diagram(args['diagram_file'], graph)


if __name__ == '__main__':
    sys.exit(main())

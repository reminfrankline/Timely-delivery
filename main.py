from flask import Flask, render_template, request
import requests
import folium
from datetime import datetime
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

app = Flask(__name__)

API_KEY = "API_KEY"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/optimize", methods=["POST"])
def optimize_route():
    locations = request.form.getlist("locations")
    priorities = request.form.getlist("priorities")
    locations_with_priorities = [{"name": loc, "priority": int(prio)} for loc, prio in zip(locations, priorities)]

    # Sort locations by priority
    locations_with_priorities.sort(key=lambda x: x["priority"])
    sorted_locations = [loc["name"] for loc in locations_with_priorities]

    # Create distance matrix
    distance_matrix, coordinates = create_distance_matrix(sorted_locations)

    # Solve TSP
    route = solve_tsp(distance_matrix)

    # Create map
    route_map, map_file_name = create_map(sorted_locations, coordinates, route)

    # Return details
    optimized_route = [sorted_locations[i] for i in route]
    return render_template(
        "route_details.html",
        route=optimized_route,
        api_key=API_KEY,
    )


def create_distance_matrix(locations):
    n = len(locations)
    distance_matrix = [[0] * n for _ in range(n)]
    coordinates = {}

    for i in range(n):
        for j in range(n):
            if i != j:
                url = (
                    f"https://maps.googleapis.com/maps/api/directions/json?"
                    f"origin={locations[i]}&destination={locations[j]}"
                    f"&key={API_KEY}"
                )
                response = requests.get(url)
                if response.status_code == 200:
                    data = response.json()
                    leg = data["routes"][0]["legs"][0]
                    distance_matrix[i][j] = leg["distance"]["value"]
                    if locations[i] not in coordinates:
                        coordinates[locations[i]] = (
                            leg["start_location"]["lat"],
                            leg["start_location"]["lng"],
                        )
                else:
                    print(f"API Request failed. status code: {response.status_code}")

    return distance_matrix, coordinates


def solve_tsp(distance_matrix):
    num_locations = len(distance_matrix)
    manager = pywrapcp.RoutingIndexManager(num_locations, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return distance_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solution = routing.SolveWithParameters(search_parameters)
    if solution:
        route = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        return route
    else:
        print("No solution found!")
        return []


def create_map(locations, coordinates, route):
    map_center = coordinates[locations[0]]
    route_map = folium.Map(location=map_center, zoom_start=10)

    # Add markers and polylines
    for loc in locations:
        folium.Marker(coordinates[loc], popup=loc).add_to(route_map)

    for i in range(len(route) - 1):
        start = coordinates[locations[route[i]]]
        end = coordinates[locations[route[i + 1]]]
        folium.PolyLine([start, end], color="blue", weight=5).add_to(route_map)

    # Generate a unique file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    map_file_name = f"static/route_map_{timestamp}.html"
    route_map.save(map_file_name)

    return route_map, map_file_name


if __name__ == "__main__":
    app.run(debug=True)


var evtSource = null;

function receiveStatusEvent(event) {
    var main_box = document.getElementById('main_box');
    var old_container = main_box.childNodes[0];
    var new_container = document.createElement("div");

    var data = JSON.parse(event.data);

    var num_tasks = data.task_statuses.length;
    for (var i=0; i<num_tasks; ++i) {
        var task = data.task_statuses[i];
        var elem = document.createElement("div");
        var classNames = "task ";
        var text = task.name;
        
        if (task.running) {
            classNames += "running";
        }
        else if (task.error) {
            classNames += "error";
        }
        else if (task.completed) {
            classNames += "completed";
        }
        
        if (task.status) {
            text += ": " + task.status;
        }

        elem.innerHTML = text;
        elem.className = classNames;
        new_container.appendChild(elem);
    }

    main_box.replaceChild(new_container, old_container);

    if (data.completed) {
        var completion_box = document.getElementById("completion_box");
        var project_title = document.getElementById("completion_project_title");
        project_title.innerHTML = data.project_title;
        completion_box.style.display = "block"; // Un-hide
    }
    else if (data.error) {
        var error_box = document.getElementById("error_box");
        var project_title = document.getElementById("error_project_title");
        project_title.innerHTML = data.project_title;
        error_box.style.display = "block";
    }
}

function shutdownStream(event) {
    evtSource.close();
}

function init(evtSourceUri) {
    document.getElementById("container").innerHTML = "Loading status...";
    evtSource = new EventSource(evtSourceUri);
    haveLoadedTasks = false;
    evtSource.addEventListener("status", receiveStatusEvent);
    evtSource.addEventListener("shutdown", shutdownStream);
}

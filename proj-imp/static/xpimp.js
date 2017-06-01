function startJobStatus(evtSourceUri) {
    evtSource = new EventSource(evtSourceUri);
    haveLoadedTasks = false;
    evtSource.addEventListener(//TODO: find func. signature 
        function(event) {
            status_area = document.getElementById('status_area');
            data = JSON.parse(event.data);
            if (data.completed) {
                evtSource.disconnect();
            }
        }
    );
}

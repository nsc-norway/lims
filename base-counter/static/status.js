
var eventSource = new EventSource("/status");
var updateHandlers = []

function runBaseCounter(span, run_id) {
	var bc = {
		'run_id': run_id,
		'span': span,
		'update_time': 0,
		'finished': false,
		'data': {},
		'update': function(e) {
			this.data = JSON.parse(e.data);
		},
		'refresh': function() {
			span.innerHTML = this.basecount;
			return this.data.finished;
		}
	};
	eventSource.addEventListener("run." + run_id, bc.update);
	updateHandlers.push(bc.refresh);
}

$().ready(function() {
	var span = document.getElementById("base-count");
	r = runBaseCounter(span, "160329_M01132_0133_000000000-AMY9J");
});

function updateCount() {
	for (var i = updateHandlers.length; i >= 0; i--) {
		if (!updateHandlers[i]()) {
			updateHandlers.pop();
		}
	}
}

function refresher() {
	updateCount();
	window.requestAnimationFrame(refresher);
}


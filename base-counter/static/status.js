
var eventSource = new EventSource("/status");
var refreshHandlers = []

function runBaseCounter(span, run_id) {
	var bc = {
		'run_id': run_id,
		'span': span,
		'update_time': 0,
		'basecount': 0,
		'data': {'basecount': 0, 'rate': 0, 'finished': 0},
		'update': function(e) {
			this.data = JSON.parse(e.data);
		},
		'refresh': function(time) {
			// Update handler
			var target = this.data.rate * (time - this.update_time) + this.data.basecount;
			this.basecount = target;
			span.innerHTML = this.basecount;
			return !this.data.finished;
		}
	};
	eventSource.addEventListener("run." + run_id, bc.update.bind(bc));
	bc.refresh(0);
	refreshHandlers.push(bc.refresh.bind(bc));
}

$().ready(function() {
	var span = document.getElementById("base-count");
	r = runBaseCounter(span, "160329_M02980_0056_000000000-AMT90");
	refresher();
});

function updateCount() {
	var time = new Date().getTime();
	for (var i = refreshHandlers.length-1; i >= 0; i--) {
		if (!refreshHandlers[i](time)) {
			refreshHandlers.pop();
		}
	}
}

function refresher() {
	updateCount();
	window.requestAnimationFrame(refresher);
}


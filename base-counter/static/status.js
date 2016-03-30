
var eventSource = new EventSource("/status");
var refreshHandlers = []

function runBaseCounter(span, run_id) {
	var bc = {
		'run_id': run_id,
		'span': span,
		'update_time': 0,
		'basecount': 0,
		'data': {'basecount': 0, 'rate': 0},
		'update': function(e) {
			this.data = JSON.parse(e.data);
		},
		'refresh': function(time) {
			// Update handler
			var target = (this.data.rate * time - this.update_time) + this.data.basecount;
			this.basecount = target;
			span.innerHTML = this.basecount;
			return !this.data.finished;
		}
	};
	eventSource.addEventListener("run." + run_id, bc.update);
	bc.refresh(0);
	refreshHandlers.push(bc);
}

$().ready(function() {
	var span = document.getElementById("base-count");
	r = runBaseCounter(span, "160329_M01132_0133_000000000-AMY9J");
	//refresher();
	updateCount();
});

function updateCount() {
	var time = new Date().getTime();
	for (var i = refreshHandlers.length-1; i >= 0; i--) {
		if (!refreshHandlers[i].refresh(time)) {
			refreshHandlers.pop();
		}
	}
}

function refresher() {
	updateCount();
	window.requestAnimationFrame(refresher);
}


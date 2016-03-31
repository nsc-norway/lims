
var refreshHandlers = []

function runBaseCounter(span, run_id) {
	var eventSource = new EventSource("/status/runs/" + run_id);
	var bc = {
		'run_id': run_id,
		'span': span,
		'update_time': 0,
		'basecount': 0,
		'data': {'basecount': 0, 'rate': 0, 'active': 1},
		'update': function(e) {
			this.data = JSON.parse(e.data);
			this.update_time = new Date().getTime();
			if (!this.data.active) {
				eventSource.close();
			}
		},
		'refresh': function(time) {
			// Update handler
			var rate_comp = this.data.rate * (time - this.update_time) / 1000.0;
			var target = rate_comp + this.data.basecount;
			this.basecount = Math.round(target);
			span.innerHTML = this.basecount.toLocaleString();
			return this.data.active;
		}
	};
	eventSource.onmessage = bc.update.bind(bc);
	refreshHandlers.push(bc.refresh.bind(bc));
}

$().ready(function() {
	var span = document.getElementById("base-count");
	var runlist = [];
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



var seqStatusApp = angular.module('seqStatusApp', []);

var ICONS = {
	'hiseq': 'graphics/hiseq-2500.png',
	'hiseqx':	'graphics/hiseq-x.png',
	'nextseq':	'graphics/nextseq.png',
	'hiseq3k': 'graphics/hiseq-4000.png',
	'hiseq4k': 'graphics/hiseq-4000.png',
	'miseq':	'graphics/miseq.png'
	};

var TYPES = {
	'hiseq': 'HiSeq 2500',
	'hiseqx':	'HiSeq X',
	'nextseq':	'NextSeq',
	'hiseq3k': 'HiSeq 3000',
	'hiseq4k': 'HiSeq 4000',
	'miseq':	'MiSeq'
	};


function Run(runId) {
	var runObj = {
		// Base counter object
		'id': runId,
		'updateTime': 0,
		'basecount': 0,
		'data': {'basecount': 0, 'rate': 0, 'finished': 0, 'cancelled': 0},
		'update': function(data) {
			this.data = data;
			this.updateTime = new Date().getTime();
			if (this.data.finished || this.data.cancelled) {
				this.basecount = Math.round(this.data.basecount);
			}
		},
		'refresh': function(time) {
			// Update handler
			if (!this.data.finished && !this.data.cancelled) {
				var rate_comp = this.data.rate * ((time - this.updateTime) / 1000.0);
				var target = rate_comp + this.data.basecount;
				this.basecount = Math.round(target);
			}
			else {
				this.basecount = this.data.basecount;
			}
		}
	};
	return runObj;
}

function GlobalBaseCounter() {
	var bc = {
		'basecount': 0,
		'data': {'count': 0, 'rate': 0},
		'updateTime': 0,
		'refresh': function(time) {
			var rate_comp = this.data.rate * ((time - this.updateTime) / 1000.0);
			var target = rate_comp + this.data.count;
			this.basecount = Math.round(target);
		},
		'update': function(event) {
			this.data = JSON.parse(event.data);
			this.updateTime = new Date().getTime();
		}
	}
	return bc;
}


seqStatusApp.controller('SeqStatusController', function($scope) {

	$scope.machines = {}

	$scope.updateMachineList = function(event) {
		var machineList = JSON.parse(event.data);
		var newMachines = {}
		for (var i=0; i<machineList.length; ++i) {
			var machine = machineList[i];
			machine.typeName = TYPES[machine.type];
			machine.icon = ICONS[machine.type];

		  machine.runs = {}
			for (var j=0; j<machine.run_ids.length; ++j) {
				var runId = machine.run_ids[j];
				var oldRun = $scope.machines[machine.id] && $scope.machines[machine.id].runs[runId];
				if (oldRun) {
					machine.runs[runId] = oldRun;
				}
				else {
					machine.runs[runId] = Run(runId);
				}
			}
			newMachines[machine.id] = machine;
		}
		$scope.machines = newMachines;
	};

	$scope.updateRun = function(event) {
		var runData = JSON.parse(event.data);
	};

	// Initialise gauge
	var target = document.getElementById("gauge");
	$scope.gauge = new Gauge(target);
	$scope.gauge.maxValue = 37;

	$scope.globalBaseCounter = GlobalBaseCounter();

	var eventSource = new EventSource('/status');
	eventSource.addEventListener('basecount', function(event) {
			$scope.globalBaseCounter.update(event);
			$scope.megaBaseRate = $scope.globalBaseCounter.data.rate / 1e6;
			$scope.gauge.set($scope.megaBaseRate);
	});

	eventSource.addEventListener('run_status', function(event) {
		var data = JSON.parse(event.data);
		var machine = $scope.machines[data.machine_id];
		if (machine) {
			var run = machine.runs[data.run_id];
			if (run) {
				run.update(data);
			}
		}
	});
	eventSource.addEventListener('machine_list', function(event) {
		$scope.$apply($scope.updateMachineList.bind(this, event));
	});

	$scope.refresh = function() {
		time = (new Date()).getTime();
		for (var machine_id in $scope.machines) {
			for (var run_id in $scope.machines[machine_id].runs) {
				$scope.machines[machine_id].runs[run_id].refresh(time);
			}
		}
		$scope.globalBaseCounter.refresh(time);
		setTimeout(window.requestAnimationFrame.bind(window, refresher), 0);
	}

	function refresher() {
		$scope.$apply($scope.refresh());
	}

	$scope.refresh();
});

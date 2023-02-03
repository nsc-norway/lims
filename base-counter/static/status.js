
var seqStatusApp = angular.module('seqStatusApp', []);

var ICONS = {
	'hiseq': 'graphics/hiseq-2500.png',
	'hiseqx':	'graphics/hiseq-x.png',
	'nextseq':	'graphics/nextseq.png',
	'hiseq3k': 'graphics/hiseq-4000.png',
	'hiseq4k': 'graphics/hiseq-4000.png',
	'miseq':	'graphics/miseq.png',
	'novaseq':	'graphics/novaseq.png',
	'mystery':	'graphics/mystery.png',
	};

var TYPES = {
	'hiseq': 'HiSeq 2500',
	'hiseqx':	'HiSeq X',
	'nextseq':	'NextSeq',
	'hiseq3k': 'HiSeq 3000',
	'hiseq4k': 'HiSeq 4000',
	'miseq':	'MiSeq',
	'novaseq':	'NovaSeq',
	'mystery':	'????',
	};

var statusEventSource = null;

seqStatusApp.factory('statusEventSource', function() {
	if (statusEventSource == null) {
	  statusEventSource = new EventSource('../status');
	}
	return statusEventSource;
});

window.onunload = function() {
    if (statusEventSource != null) {
        statusEventSource.close();
    }
};

function Machine(dataObj) {
	var machine = dataObj;
	machine.installed = machine.type && machine.type.substring(0,1) != "-";
	if (!machine.installed) {
		machine.type = machine.type.substring(1);
	}
	machine.typeName = TYPES[machine.type];
	if ((machine.name == "Nelly") || (machine.name == "Newton")) {
		machine.typeName = "NextSeq Dx";
	}
	machine.icon = ICONS[machine.type];
	machine.runs = {};
	return machine;
}

function Run(runId) {
	var runObj = {
		// Base counter object
		'id': runId,
		'updateTime': 0,
		'basecount': 0,
		'data': {'basecount': 0, 'rate': 0, 'finished': 0, 'cancelled': 0, 'run_type': 'general'},
		'completionPct': 0,
		'update': function(data) {
			this.data = data;
			this.updateTime = new Date().getTime();
			if (this.data.finished || this.data.cancelled) {
				this.basecount = Math.round(this.data.basecount);
			}
			if (this.data.total_cycles != 0) {
				this.completionPct = this.data.current_cycle * 100.0 / this.data.total_cycles;
			}
			else {
				this.completionPct = 0;
			}
			this.useClass = getRunProgressCssClass(data);
		},
		'refresh': function(time) {
			// Update handler
			if (!this.data.finished && !this.data.cancelled) {
				var rate_comp = this.data.rate * (time - this.updateTime) / 1000.0;
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


function getRunProgressCssClass(run_data) {
	if (run_data.cancelled) return 'run-failed';
	if (run_data.finished) return 'run-completed';
	if (run_data.run_type == "nipt") return 'nipt';
	return 'running';
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


seqStatusApp.controller('SeqStatusController', function($scope, statusEventSource) {

	$scope.machines = {}

	$scope.updateMachineList = function(event) {
		var machineList = JSON.parse(event.data);
		var newMachines = {};
		var machineTypeOrderedList = [];
		var machineListForType = [];
		var prevType = null;
		for (var i=0; i<machineList.length; ++i) {
			var machine = Machine(machineList[i]);

			if (prevType != null && machine.type != prevType) {
				machineTypeOrderedList.push(machineListForType);
				machineListForType = [];
			}
			prevType = machine.type;

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
			machineListForType.push(machine);
		}
		machineTypeOrderedList.push(machineListForType);

		$scope.machines = newMachines;
		$scope.machineTypeOrderedList = machineTypeOrderedList;
	};

	// Initialise gauge
	var target = document.getElementById("gauge");
	$scope.gauge = new Gauge(target);
	$scope.gauge.maxValue = 300;

	$scope.globalBaseCounter = GlobalBaseCounter();

	statusEventSource.addEventListener('basecount', function(event) {
			$scope.globalBaseCounter.update(event);
			$scope.xBaseRate = $scope.globalBaseCounter.data.rate / 1e6;
			$scope.megaBaseRate = $scope.globalBaseCounter.data.rate / 1e6;
			if ($scope.xBaseRate > 0.5) {
				$scope.baseRateUnit = "Mbases/s"
			}
			else {
				$scope.xBaseRate = $scope.globalBaseCounter.data.rate / 1e3;
				$scope.baseRateUnit = "kbases/s"
			}
			$scope.gauge.set($scope.megaBaseRate);
	});

	statusEventSource.addEventListener('run_status', function(event) {
		var data = JSON.parse(event.data);
		var machine = $scope.machines[data.machine_id];
		if (machine) {
			var run = machine.runs[data.run_id];
			if (run) {
				run.update(data);
			}
		}
	});
	statusEventSource.addEventListener('machine_list', function(event) {
		$scope.$apply($scope.updateMachineList.bind(this, event));
	});

	$scope.refresh = function() {
		var time = (new Date()).getTime();
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

seqStatusApp.controller('GlobalBaseCounterController', function($scope, statusEventSource) {

	// Initialise gauge
	var target = document.getElementById("gauge");
	$scope.gauge = new Gauge(target);
	$scope.gauge.maxValue = 37;

	$scope.globalBaseCounter = GlobalBaseCounter();

	statusEventSource.addEventListener('basecount', function(event) {
			$scope.globalBaseCounter.update(event);
			$scope.xBaseRate = $scope.globalBaseCounter.data.rate / 1e6;
			$scope.megaBaseRate = $scope.globalBaseCounter.data.rate / 1e6;
			if ($scope.xBaseRate > 0.5) {
				$scope.baseRateUnit = "Mbases/s"
			}
			else {
				$scope.xBaseRate = $scope.globalBaseCounter.data.rate / 1e3;
				$scope.baseRateUnit = "kbases/s"
			}
			$scope.gauge.set($scope.megaBaseRate);
	});
	$scope.refresh = function() {
		var time = (new Date()).getTime();
		$scope.globalBaseCounter.refresh(time);
		setTimeout(window.requestAnimationFrame.bind(window, refresher), 0);
	}

	function refresher() {
		$scope.$apply($scope.refresh());
	}

	$scope.refresh();

});


seqStatusApp.controller('SingleMachineController', function($scope, $location) {

  var statusEventSource = new EventSource("../status");

	$scope.machine = {runs: {}};
	$scope.machine_id = function() {
		return $location.path().replace("/", "");
	}

	var machineList = [];

	$scope.updateMachine = function(event) {
		if (event != null) {
			 machineList = JSON.parse(event.data);
		}

		for (var i=0; i<machineList.length; ++i) {
			var machine = machineList[i];

			if ($scope.machine_id() == machine.id) {
				$scope.machine = Machine(machine);
				for (var j=0; j<machine.run_ids.length; ++j) {
					var runId = machine.run_ids[j];
					var oldRun = $scope.machine.runs[runId];
					if (oldRun) {
						$scope.machine.runs[runId] = oldRun;
					}
					else {
						$scope.machine.runs[runId] = Run(runId);
					}
				}
			}
		}
	};

	statusEventSource.addEventListener('run_status', function(event) {
		var data = JSON.parse(event.data);
		if (data.machine_id == $scope.machine_id()) {
			var run = $scope.machine.runs[data.run_id];
			if (run) {
				run.update(data);
			}
		}
	});

	statusEventSource.addEventListener('machine_list', function(event) {
		$scope.$apply($scope.updateMachine.bind(this, event));
	});

	$scope.refresh = function() {
		var time = (new Date()).getTime();
		for (var run_id in $scope.machine.runs) {
			$scope.machine.runs[run_id].refresh(time);
		}
		setTimeout(window.requestAnimationFrame.bind(window, refresher), 0);
	}

	// Look for URL changes
	$scope.$watch('machine_id()', $scope.updateMachine.bind(this, null));

	function refresher() {
		$scope.$apply($scope.refresh());
	}

	$scope.refresh();

});



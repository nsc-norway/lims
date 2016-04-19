
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



function run(runId) {
	var eventSource = new EventSource("/status/runs/" + runId);
	var runObj = {
		// Base counter object
		'id': runId,
		'updateTime': 0,
		'basecount': 0,
		'data': {'basecount': 0, 'rate': 0, 'active': 1},
		'update': function(e) {
			this.data = JSON.parse(e.data);
			this.updateTime = new Date().getTime();
			if (!this.data.active) {
				eventSource.close();
			}
		},
		'refresh': function(time) {
			// Update handler
			var rate_comp = this.data.rate * (time - this.updateTime) / 1000.0;
			var target = rate_comp + this.data.basecount;
			this.basecount = Math.round(target);
		}
	};
	eventSource.onmessage = runObj.update.bind(runObj);
	return runObj;
}


seqStatusApp.controller('SeqStatusController', function($scope) {

	$scope.machines = {}

	$scope.update = function(event) {
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
					machine.runs[runId] = run(runId);
				}
			}
			newMachines[machine.id] = machine;
		}
		$scope.machines = newMachines;
	};

	var source = new EventSource('/status/machines');
	source.onmessage = function(event) {
		// Master updater: instrument list
		$scope.$apply($scope.update(event));
	};

	$scope.refresh = function() {
		time = (new Date()).getTime();
		for (var machine_id in $scope.machines) {
			for (var run_id in $scope.machines[machine_id].runs) {
				$scope.machines[machine_id].runs[run_id].refresh(time);
			}
		}
	}

	function refresher() {
		$scope.$apply($scope.refresh());
		window.requestAnimationFrame(refresher);
	}

	//refresher();
});

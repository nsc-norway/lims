
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
				eventSource.close();
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

function globalBaseCounter() {
	var eventSource = new EventSource('/status/count')
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

	eventSource.onmessage = bc.update.bind(bc);
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
					machine.runs[runId] = run(runId);
				}
			}
			newMachines[machine.id] = machine;
		}
		$scope.machines = newMachines;
	};

	$scope.updateRun = function(event) {
		var runData = JSON.parse(event.data);

	};

	//$scope.global = globalBaseCounter();

	var source = new EventSource('/status/machines');
	source.onmessage = function(event) {
		// Master updater: instrument list
		$scope.$apply($scope.updateMachineList(event));
	};


	$scope.refresh = function() {
		time = (new Date()).getTime();
		for (var machine_id in $scope.machines) {
			for (var run_id in $scope.machines[machine_id].runs) {
				$scope.machines[machine_id].runs[run_id].refresh(time);
			}
		}
		//$scope.global.refresh(time);
	}

	function refresher() {
		$scope.$apply($scope.refresh());
		window.requestAnimationFrame(refresher);
	}

	//refresher();
});

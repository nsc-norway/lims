
var fakeRunApp = angular.module('fakeRunApp', []);


fakeRunApp.controller('FakeRunController', function($scope, $http) {

	$http.get('../machines').success(function(machines) {
		$scope.machines = machines;
	});

	function refreshRunList() {
		$http.get('../fake-runs').success(function(fakes) {
			$scope.fakeRuns = fakes.runs;
		});
	}

	function finished(data) {
		$scope.status = data.statusText;
		refreshRunList();
	}

	$scope.addRun = function() {
		$http.post('../fake', {
			'machine': $scope.machine,
			'cycles': $scope.cycles,
			'start_cycle': $scope.start_cycle
		}).then(finished, finished);
	}

	$scope.deleteRun = function() {
		$http.post('../delete', {
			'id': $scope.delRun
		}).then(finished, finished);
	}

	refreshRunList();
});

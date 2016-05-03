
var fakeRunApp = angular.module('fakeRunApp', []);


fakeRunApp.controller('FakeRunController', function($scope, $http) {

	$http.get('../machines').success(function(machines) {
		$scope.machines = machines;
	});

	function finished(data) {
		$scope.status = data.statusText;
	}

	$scope.addRun = function() {
		$http.post('../fake', {
			'machine': $scope.machine,
			'cycles': $scope.cycles,
			'start_cycle': $scope.start_cycle
		}).then(finished, finished);
	}

});

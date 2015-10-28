var reagentsUi = angular.module('reagentsUi', []);

reagentsUi.controller('scanningController', function ($scope) {
	$scope.saving = false;
	$scope.ref = "";
	$scope.lot = "";
	$scope.rgt = "";
	$scope.kit = object();
	$scope.lotinfo = object(); 
	var defaultDate = new Date();
	$scope.lotinfo.expiryDate = new Date();

	  $scope.phones = [
	    {'name': 'Nexus S',
	     'snippet': 'Fast just got faster with Nexus S.'},
	    {'name': 'Motorola XOOM™ with Wi-Fi',
	     'snippet': 'The Next, Next Generation tablet.'},
	    {'name': 'MOTOROLA XOOM™',
	     'snippet': 'The Next, Next Generation tablet.'}
	  ];
});



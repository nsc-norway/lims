var app = angular.module('reagentsUi', []);

app.controller('scanningController', function ($scope, $timeout) {
	$scope.busy = false;
	$scope.ref = "";
	$scope.lotnumber = "";
	$scope.rgt = "";
	$scope.scanMode = true;
	$scope.kit = {};
	$scope.lotinfo = {}; 
	$timeout(function (){
		$scope.$broadcast("focusRef");
	});
	$scope.ref_change = function() {
		alert("Changed to " + $scope.ref);
	};
});

app.directive('focusOn', function() {
   return function(scope, elem, attr) {
      scope.$on(attr.focusOn, function(e) {
          elem[0].focus();
      });
   };
});






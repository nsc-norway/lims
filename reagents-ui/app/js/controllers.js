var app = angular.module('reagentsUi', ['ngResource']);

function resetInputFields($scope) {
	$scope.lotnumber = "";
	$scope.rgt = "";
	$scope.scanMode = true;
	$scope.error = false;
}

function resetDetails($scope) {
	$scope.saved = false;
	$scope.submitted = false;
	$scope.kit = {ref: "", found:false, requestLotName: false};
	$scope.lot = {lotnumber: "", known: false};
}

app.factory('Kit', function($resource) {
	return $resource(
		"../kits/:ref"
	);
});

function dateConverterInterceptor(response) {
	var data = response.data, key, value;
	for (key in data) {
		if (!data.hasOwnProperty(key) && // don't parse prototype or non-string props
				toString.call(data[key]) !== '[object String]') continue;
		value = Date.parse(data[key]); // try to parse to date
		if (!isNaN(value)) {
			data[key] = value;
		}
	}
	return response;
}

app.factory('Lot', function($resource) {
	return $resource(
		"../lots/:ref/:lotnumber", {'ref':'@ref', 'lotnumber': '@lotnumber'}, {
			'get': {interceptor: {response: dateConverterInterceptor}},
			'put': {method: 'POST'}
		}
	);
});

app.controller('scanningController', function ($scope, $timeout, Kit, Lot) {

	resetInputFields($scope);
	resetDetails($scope);
	$scope.ref = "";

	$timeout(function (){
		$scope.$broadcast("focusRef");
	});

	$scope.refChanged = function() {
		resetInputFields($scope);
		if ($scope.ref != "") {
			resetDetails($scope);
			var ref = $scope.ref;
			$scope.submitted = false;
			$scope.saved = false;
			$scope.kit = Kit.get({'ref': ref},
							function() {
								$scope.$broadcast("focusLot");
							},
							function (httpResponse) {
								if (httpResponse.status == 404) {
									$scope.kit.found = false;
								}
								else {
									alert("Communication error or bug, sorry.");
								}
							});
		}
	};

	$scope.lotChanged = function() {
		if ($scope.lot.lotnumber == "" && $scope.lotnumber.length > 3) {
					if ($scope.kit.requestLotName) {
						$scope.$broadcast("focusRgt");
					}
					else {
						$scope.$broadcast("focusDate");
					}
		}
		else {
			$scope.scanMode = false;
		}
		if ($scope.lotnumber != "") {
			$scope.lot = Lot.get({'ref': $scope.ref, 'lotnumber': $scope.lotnumber},
			function() {
				if ($scope.lot.known && !$scope.kit.requestLotName) {
					if ($scope.scanMode) {
						$scope.saveLot($scope);
					}
				}
				if ($scope.lot.known && $scope.kit.requestLotName) {
					$scope.$broadcast("focusRgt");
				}
			});
		}
		else {
			$scope.lot = {lotnumber: "", known: false};
		}
	};

	$scope.rgtChanged = function() {
		if (! ($scope.lot.uid == "" && $scope.rgt.length > 3)) {
			$scope.scanMode = false;
		}
		$scope.lot.uid = $scope.rgt;
		if ($scope.rgt != "" && $scope.scanMode) {
			$scope.saveLot($scope);
		}
	};

	$scope.saveLot = function() {
		var lot = $scope.lot;
		resetInputFields($scope);
		$scope.ref = "";
		$scope.$broadcast("focusRef");
		$scope.submitted = true;
		lot.$save({},
			function() {
				$scope.saved = true;
			}, function(error) {
				alert("There was an error saving the lot.");
				$scope.submitted = false;
				$scope.confirmSave = true;
				$scope.error = true;
				document.getElementById('error-frame').src = "data:text/html;charset=utf-8," + escape(error.data);
			});
	};

});

app.directive('focusOn', function() {
   return function(scope, elem, attr) {
      scope.$on(attr.focusOn, function(e) {
          elem[0].focus();
      });
   };
});

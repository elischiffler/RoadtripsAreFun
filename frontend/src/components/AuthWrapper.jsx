import React, { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";

const AuthWrapper = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const token = sessionStorage.getItem("accessToken");
    // Routes that can be accessed if user is unauthorized
    const allowedRoutes = ["/", "/login", "/signup"];
    // Check if the pathname of your current location is in allowedRoutes
    const isAllowedRoute = allowedRoutes.includes(location.pathname);

    // If the user is not authenticated and tries to access a route other than "/", "/login", or "/signup"
    if (!token && !isAllowedRoute) {
      navigate("/login");
    }
  }, [navigate, location]);

  return <>{children}</>;
};

export default AuthWrapper;

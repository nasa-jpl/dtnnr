import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

const AuthContext = createContext(null);

export async function fetchWhoami() {
  // TODO: fix this once API gets its authn endpoint back
  // let response = await fetch(`/auth/whoami`, {
  //   headers: {
  //     'Content-Type': 'application/json',
  //   }
  // });
  // let cuser = null;
  // if (response.ok) {
  //   cuser = await response.json();
  // }
  // return cuser;
  return 'foo@example.com';
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);

  // This function is defined outside of the useEffect(), so it can be used
  // after logging in / logging out.
  const checkWhoami = useCallback(async () => {
    let cuser = await fetchWhoami();
    setCurrentUser(cuser);
  }, []);

  useEffect(() => {
    checkWhoami();
  }, [checkWhoami]);

  const contextValue = useMemo(
    () => ({
      currentUser,
      checkWhoami,
    }),
    [currentUser, checkWhoami],
  );

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  );
}

export default AuthContext;
